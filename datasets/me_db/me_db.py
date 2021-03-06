"""me - Aggregate health and time tracking data.

Usage:

  bazel run -c opt //datasets/me_db --
      --inbox=$HOME/inbox --db="sqlite:///$HOME/me.db"
"""
import datetime
import multiprocessing
import pathlib
import time
import typing

import humanize
import sqlalchemy as sql
from absl import app
from absl import flags
from absl import logging
from sqlalchemy.dialects import mysql
from sqlalchemy.ext import declarative

from datasets.me_db import importers
from datasets.me_db import me_pb2
from datasets.me_db.providers.health_kit import health_kit
from datasets.me_db.providers.life_cycle import life_cycle
from datasets.me_db.providers.timing import timing
from datasets.me_db.providers.ynab import ynab
from labm8 import labdate
from labm8 import sqlutil


FLAGS = flags.FLAGS

flags.DEFINE_string('inbox', None, 'Path to inbox.')
flags.DEFINE_string('db', 'me.db', 'Path to database.')
flags.DEFINE_bool('replace_existing', False,
                  'Remove existing database, if it exists.')

Base = declarative.declarative_base()

# The list of inbox importers. An inbox importer is a function that takes a
# path to a directory (the inbox) and a Queue. The function, when called, must
# place a single SeriesCollection proto on the queue.
INBOX_IMPORTERS: typing.List[importers.InboxImporter] = [
  health_kit.ProcessInboxToQueue,
  life_cycle.ProcessInboxToQueue,
  timing.ProcessInboxToQueue,
  ynab.ProcessInboxToQueue,
]


class Measurement(Base):
  """The measurements table.

  A row in the measurements table is a concatenation of a me.Measurement proto,
  and the non-measurement fields from a me.Series proto.
  """
  __tablename__ = 'measurements'

  id: int = sql.Column(sql.Integer, primary_key=True)

  family: str = sql.Column(sql.String(512), nullable=False)
  series: str = sql.Column(sql.String(512), nullable=False)
  group: str = sql.Column(sql.String(512), nullable=False)
  date: datetime.datetime = sql.Column(
      sql.DateTime().with_variant(mysql.DATETIME(fsp=3), 'mysql'),
      nullable=False)
  value: int = sql.Column(sql.Integer, nullable=False)
  unit: str = sql.Column(sql.String(512), nullable=False)
  source: str = sql.Column(sql.String(512), nullable=False)

  def __repr__(self):
    return f"{self.family}:{self.series} {self.value} {self.unit} {self.date}"


def MeasurementsFromSeries(series: me_pb2.Series) -> typing.List[Measurement]:
  """Create a list of measurements from a me.Series proto."""
  return [
    Measurement(series=series.name,
                date=labdate.DatetimeFromMillisecondsTimestamp(
                    m.ms_since_unix_epoch),
                family=series.family,
                group=m.group,
                value=m.value,
                unit=series.unit,
                source=m.source)
    for m in series.measurement]


class Database(sqlutil.Database):

  def __init__(self, url: str):
    super(Database, self).__init__(url, Base)

  @staticmethod
  def AddSeriesCollection(session: sqlutil.Session,
                          series_collection: me_pb2.SeriesCollection) -> int:
    """Import the given series_collections to database."""
    num_measurements = 0
    for series in series_collection.series:
      num_measurements += len(series.measurement)
      logging.info('Importing %s %s:%s measurements',
                   humanize.intcomma(len(series.measurement)), series.family,
                   series.name)
      session.add_all(MeasurementsFromSeries(series))
    return num_measurements

  def ImportMeasurementsFromInboxImporters(
      self, inbox: pathlib.Path, inbox_importers: typing.Iterator[
        importers.InboxImporter] = INBOX_IMPORTERS):
    """Import and commit measurements from inbox directory."""
    start_time = time.time()
    queue = multiprocessing.Queue()

    # Start each importer in a separate process.
    processes = []
    for importer in inbox_importers:
      process = multiprocessing.Process(target=importer, args=(inbox, queue))
      process.start()
      processes.append(process)
    logging.info('Started %d importer processes', len(processes))

    # Get the results of each process as it finishes.
    num_measurements = 0
    for _ in range(len(processes)):
      series_collections = queue.get()
      with self.Session(commit=True) as session:
        num_measurements += self.AddSeriesCollection(
            session, series_collections)

    duration_seconds = time.time() - start_time
    logging.info('Processed %s records in %.3f seconds (%.2f rows per second)',
                 humanize.intcomma(num_measurements), duration_seconds,
                 num_measurements / duration_seconds)


def main(argv):
  if len(argv) > 1:
    raise app.UsageError('Unrecognized command line flags.')

  inbox_path = pathlib.Path(FLAGS.inbox)

  # Validate the flags paths.
  if not inbox_path.is_dir():
    raise app.UsageError(f'Inbox is not a directory: "{inbox_path}"')

  # If we are replacing an existing database, connect to it (which may include
  # creating it it), drop it, then immediately connect again (which will this
  # time create it).
  if FLAGS.replace_existing:
    db = Database(FLAGS.db)
    db.Drop(are_you_sure_about_this_flag=True)

  db = Database(FLAGS.db)
  logging.info('Using database `%s`', db.url)

  db.ImportMeasurementsFromInboxImporters(inbox_path)


if __name__ == '__main__':
  app.run(main)

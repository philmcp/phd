"""Import data from YNAB."""
import multiprocessing
import pathlib
import subprocess
import typing

from absl import app
from absl import flags

from datasets.me_db import importers
from datasets.me_db import me_pb2
from labm8 import bazelutil
from labm8 import pbutil


FLAGS = flags.FLAGS

flags.DEFINE_string('ynab_inbox', None, 'Inbox to process.')


def ProcessBudgetJsonFile(path: pathlib.Path) -> me_pb2.SeriesCollection:
  if not path.is_file():
    raise FileNotFoundError(str(path))
  try:
    return pbutil.RunProcessMessageInPlace(
        [str(
            bazelutil.DataPath(
                'phd/datasets/me_db/providers/ynab/json_budget_worker'))],
        me_pb2.SeriesCollection(source=str(path)))
  except subprocess.CalledProcessError as e:
    raise importers.ImporterError('LifeCycle', path, str(e)) from e


def ProcessInbox(inbox: pathlib.Path) -> me_pb2.SeriesCollection:
  """Process a directory of YNAB data.

  Args:
    inbox: The inbox path.

  Returns:
    A SeriesCollection message.
  """
  if not (inbox / 'ynab').is_dir():
    return me_pb2.SeriesCollection()

  files = subprocess.check_output(
      ['find', '-L', str(inbox / 'ynab'), '-name', 'Budget.yfull'],
      universal_newlines=True).rstrip().split('\n')

  # TODO(cec): There can be multiple directories for a single budget. Do we need
  # to de-duplicate them?
  files = [pathlib.Path(f) for f in files]

  series_collections = []
  if files and files[0]:
    for file in files:
      series_collections.append(ProcessBudgetJsonFile(file))
  return importers.MergeSeriesCollections(series_collections)


def ProcessInboxToQueue(inbox: pathlib.Path, queue: multiprocessing.Queue):
  queue.put(ProcessInbox(inbox))


def main(argv: typing.List[str]):
  """Main entry point."""
  if len(argv) > 1:
    raise app.UsageError("Unknown arguments: '{}'.".format(' '.join(argv[1:])))

  print(ProcessInbox(pathlib.Path(FLAGS.ynab_inbox)))


if __name__ == '__main__':
  app.run(main)

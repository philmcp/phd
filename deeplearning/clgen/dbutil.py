"""CLgen sqlite3 database utilities."""
import os
import pathlib
import re
import sqlite3
import sys
from hashlib import md5
from typing import List

import editdistance
from absl import logging

from deeplearning.clgen import errors
from deeplearning.clgen import languages
from deeplearning.clgen import package_util
from lib.labm8 import fs


def create_db(path: str, github: bool = False) -> None:
  """
  Create an empty OpenCL kernel database.

  Parameters
  ----------
  path : str
      Path to database to create.
  github : bool, optional
      Add tables for GitHub metadata.
  """
  path = os.path.expanduser(path)

  if os.path.exists(path):
    raise errors.UserError("'{}' already exists".format(path))

  db = sqlite3.connect(path)
  c = db.cursor()
  if github:
    script = package_util.sql_script('create-gh-samples-db')
  else:
    script = package_util.sql_script('create-samples-db')
  c.executescript(script)
  c.close()
  db.commit()
  db.close()


class md5sum_aggregator:
  """ sqlite3 aggregator for computing checksum of column values. """

  def __init__(self):
    self.md5 = md5()

  def step(self, value) -> None:
    self.md5.update(str(value).encode('utf-8'))

  def finalize(self) -> str:
    return self.md5.hexdigest()


class linecount_aggregator:
  """ sqlite3 aggregator for computing line count of column values. """

  def __init__(self):
    self.count = 0

  def step(self, value) -> None:
    self.count += len(value.split('\n'))

  def finalize(self) -> int:
    return self.count


def linecount(t: str) -> int:
  """
  Line count.

  Parameters
  ----------
  t : str
      String.

  Returns
  -------
  int
      Line count.
  """
  return len(t.split('\n'))


class charcount_aggregator:
  """
  sqlite3 aggregator for computing character count of column values.
  """

  def __init__(self):
    self.count = 0

  def step(self, value) -> None:
    self.count += len(value)

  def finalize(self) -> int:
    return self.count


def connect(db_path: str):
  """
  Returns a connection to a database.

  Database has additional aggregate functions:

   * MD5SUM() returns md5 of column values
   * LC() returns sum line count of text columns
   * CC() returns sum character count of text columns
   * LC_col() returns line count of text value

  Parameters
  ----------
  db_path : str
      Path to database.

  Returns
  -------
  sqlite3.Connection
      Database connection.
  """
  db = sqlite3.connect(db_path)
  db.create_aggregate("MD5SUM", 1, md5sum_aggregator)
  db.create_aggregate("LC", 1, linecount_aggregator)
  db.create_aggregate("CC", 1, charcount_aggregator)
  db.create_function("LC_col", 1, linecount)
  return db


def set_meta(path: str, key: str, value: str) -> None:
  """
  Set a value in a database's Meta table.

  If the a row with this key already exists in the table, it is replaced.

  Parameters
  ----------
  path : str
      Path to database.
  key : str
      Key name.
  value : str
      Value to insert.
  """
  db = sqlite3.connect(path)
  c = db.cursor()
  c.execute("DELETE FROM Meta WHERE key=?", (key,))
  c.execute("INSERT INTO Meta (key, value) VALUES (?,?)", (key, value))
  c.close()
  db.commit()


def get_meta(path: str, key: str) -> str:
  """
  Retrieve a value from a database's Meta table.

  Parameters
  ----------
  path : str
      Path to database.
  key : str
      Key name.

  Returns
  -------
  str
      Value. If no row matching key is found, returns empty string.
  """
  db = sqlite3.connect(path)
  c = db.cursor()
  c.execute("SELECT value FROM Meta WHERE key=?", (key,))
  v = c.fetchone()
  if v:
    return v[0]
  else:
    return ""


def get_kernel(path: str, kid: str, table: str = "PreprocessedFiles") -> str:
  """
  Retrieve a kernel from a database.

  Parameters
  ----------
  path : str
      Path to database.
  kid : str
      Kernel ID.
  table : str
      Name of table.

  Returns
  -------
  str
      Source code.
  """
  db = sqlite3.connect(path)
  c = db.cursor()
  c.execute("SELECT contents FROM {table} WHERE id=?".format(**vars()), (kid,))
  src = c.fetchone()[0]

  c.close()
  db.close()

  return src


def get_inlined_kernel(path: str, kid: str,
                       lang: languages.Language = languages.Language.OPENCL,
                       stack: List[str] = None) -> str:
  """
  Retrieve a kernel from a database and inline any includes.

  Parameters
  ----------
  path : str
      Path to database.
  kid : str
      Kernel ID.
  lang : languages.Language
      Programming language.

  Returns
  -------
  str
      Source code.
  """
  if stack is None:
    stack = []

  db = sqlite3.connect(path)
  c = db.cursor()
  c.execute(f"SELECT contents FROM ContentFiles WHERE id=?", (kid,))
  src = c.fetchone()[0]

  c.execute("SELECT path, repo_url FROM ContentMeta WHERE id=?", (kid,))
  repo_path, repo = c.fetchone()
  stack.append(repo_path)

  include_re = \
    {languages.Language.GLSL: re.compile(r'\w*#include ["<](?P<path>.*)[">]'),
     languages.Language.OPENCL: re.compile(r'\w*#include ["<](?P<path>.*)[">]'),
     languages.Language.SOLIDITY: re.compile(
       r'\w*import ["<](\./)?(?P<path>.*)[">];'), }[lang]

  outlines = []
  for line in src.split('\n'):
    match = re.match(include_re, line)
    if match:
      include_name = match.group("path")

      # try and resolve relative paths
      include_name = include_name.replace('../', '').replace('./', '')

      c.execute('SELECT path FROM contentmeta WHERE repo_url=? AND '
                f"path LIKE '%{include_name}%'", (repo,))
      repo_paths = [row[0] for row in c.fetchall()]

      if len(repo_paths):
        distances = [editdistance.eval(include_name, path) for path in
                     repo_paths]
        closest_match = repo_paths[distances.index(min(distances))]

        if closest_match in stack:
          outlines.append(
            '// [FETCH] ignored recursive include: ' + include_name)
        else:
          logging.debug("closest match to %s is %s", include_name,
                        closest_match)

          c.execute("SELECT id FROM contentmeta WHERE path=?", (closest_match,))
          closest_kid = c.fetchone()[0]

          include_src = get_inlined_kernel(path, closest_kid, lang, stack)
          outlines.append('// [FETCH] include: ' + include_name)
          outlines.append(include_src)
          outlines.append('// [FETCH] eof(' + include_name + ')')
      else:
        outlines.append('// [FETCH] 404 not found: ' + include_name)
    else:
      outlines.append(line)

  c.close()
  db.close()

  return "\n".join(outlines)


def set_version_meta(path: str) -> None:
  """
  Set the "version" key in an database.

  This is useful for marking version requirements of specific datasets, e.g.
  a databse schema which requires a particular CLgen version, or a scheme
  which is likely to change in the future.

  Parameters
  ----------
  path : str
      Path to database.
  version : str, optional
      Version value (defaults to CLgen version).
  """
  set_meta(path, "version", "master")


def version_meta_matches(path: str) -> bool:
  """
  Check that the "version" key in a database matches the expected value.

  If the database does not have a "version" key in the Meta table, returns
  False.

  Parameters
  ----------
  path : str
      Path to database.
  version : str, optional
      Version value (defaults to CLgen version).

  Returns
  -------
  bool
      True if version in database matches expected version, else False.
  """
  return True


def run_script(path: str, script: str) -> None:
  """
  Run an SQL script on a databse.

  Parameters
  ----------
  path : str
      Path to database.
  script : str
      Name of SQL data script.
  """
  db = sqlite3.connect(path)
  c = db.cursor()
  c.executescript(package_util.sql_script(script))
  c.close()
  db.commit()
  db.close()


def is_modified(db) -> bool:
  """
  Returns whether database is preprocessed.

  Parameters
  ----------
  db : sqlite3.Connection
      Database.

  Returns
  -------
  bool
      True if database is modified, else False.
  """
  c = db.cursor()

  c.execute("SELECT value FROM Meta WHERE key='preprocessed_checksum'")
  result = c.fetchone()
  cached_checksum = result[0] if result else None

  c.execute('SELECT MD5SUM(id) FROM ContentFiles')
  checksum = c.fetchone()[0]
  c.close()

  return False if cached_checksum == checksum else checksum


def set_modified_status(db, checksum: str) -> None:
  """
  Set database preprocessed checksum.

  Parameters
  ----------
  db : sqlite3.Connection
      Database.
  checksum : str
      New preprocessed checksum.
  """
  c = db.cursor()
  c.execute("INSERT OR REPLACE INTO Meta VALUES (?,?)",
            ('preprocessed_checksum', checksum))
  db.commit()
  c.close()


def kernel_ids(db_path: str, table: str = "PreprocessedFiles") -> List[str]:
  """
  Get a list of kernel IDs.

  Parameters
  ----------
  path : str
      Database path.
  table : str, optional
      Name of table.

  Returns
  -------
  List[str]
      Kernel IDs.
  """
  db = connect(db_path)
  c = db.cursor()

  c.execute("SELECT id FROM {table}".format(**vars()))
  results = [row[0] for row in c.fetchall()]

  c.close()
  db.close()

  return results


def table_exists(db, table_name: str) -> None:
  """
  SQL table exists.

  Parameters
  ----------
  db : sqlite3.Connection
      Database.
  table_name : str
      Name of table.

  Returns
  -------
  bool
      True if table with name exists.
  """
  c = db.cursor()
  c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='" +
    table_name + "'")
  res = c.fetchone()
  c.close()
  return res and res[0]


def is_github(db) -> None:
  """
  SQL table has GitHub metadata tables.

  Parameters
  ----------
  db : sqlite3.Connection
      Database.

  Returns
  -------
  bool
      True if GitHub tables in database.
  """
  return table_exists(db, 'Repositories')


def num_good_kernels(path: str) -> int:
  """
  Fetch the number of good preprocessed kernels from dataset.

  Parameters
  ----------
  path : str
      Path to database.

  Returns
  -------
  int
      Num preprocessed kernels where status is 0.
  """
  return num_rows_in(path, "PreprocessedFiles", "WHERE status=0")


def num_rows_in(path: str, table: str, condition: str = "") -> int:
  """
  Fetch number of rows in table.

  Parameters
  ----------
  path : str
      Path to database.
  table : str
      Table ID.
  condition : str, optional
      Conditional.

  Returns
  -------
  int
      Num rows.
  """
  db = connect(path)
  c = db.cursor()
  c.execute('SELECT Count(*) FROM {table} {condition}'.format(table=table,
                                                              condition=condition))
  return c.fetchone()[0]


def cc(path: str, table: str, column: str = "Contents",
       condition: str = "") -> int:
  """
  Fetch character count of contents in table.

  Parameters
  ----------
  path : str
      Path to database.
  table : str
      Table ID.
  condition : str, optional
      Conditional.

  Returns
  -------
  int
      Num chars.
  """
  db = connect(path)
  c = db.cursor()
  c.execute("SELECT CC({column}) FROM {table} {condition}".format(column=column,
                                                                  table=table,
                                                                  condition=condition))
  return c.fetchone()[0] or 0


def lc(path: str, table: str, column: str = "Contents",
       condition: str = "") -> int:
  """
  Fetch line count of contents in table.

  Parameters
  ----------
  path : str
      Path to database.
  table : str
      Table ID.
  condition : str, optional
      Conditional.

  Returns
  -------
  int
      Num lines.
  """
  db = connect(path)
  c = db.cursor()
  c.execute("SELECT LC({column}) FROM {table} {condition}".format(column=column,
                                                                  table=table,
                                                                  condition=condition))
  return c.fetchone()[0] or 0


def remove_preprocessed(path: str) -> None:
  """
  Removes all preprocessed files from database.

  ContentFiles remain unchanged.

  Parameters
  ----------
  path : str
      Path to database.
  """
  db = connect(path)
  c = db.cursor()
  c.execute("DELETE FROM PreprocessedFiles")
  c.execute("DELETE FROM Meta WHERE key='preprocessed_checksum'")
  c.close()
  db.commit()


def remove_bad_preprocessed(db_path: str) -> None:
  """
  Remove all ugly and bad contents from PreprocessedFiles table.

  Parameters
  ----------
  db_path : str
      Dataset.
  """
  original_size = fs.du(db_path, human_readable=False)
  original_size_human_readable = fs.du(db_path, human_readable=True)
  logging.info("vacuuming %s database", original_size_human_readable)
  sys.stdout.flush()

  # Remove contents from bad or ugly preprocessed files.
  db = connect(db_path)
  c = db.cursor()
  c.execute("UPDATE PreprocessedFiles SET contents='[DELETED]' "
            "WHERE status=1 OR status=2")
  db.commit()
  c.close()
  db.close()

  db = connect(db_path)
  c = db.cursor()
  c.execute("VACUUM")
  db.commit()
  c.close()

  new_size = fs.du(db_path, human_readable=False)
  new_size_human_readable = fs.du(db_path, human_readable=True)
  reduction_ratio = (1 - (new_size / original_size)) * 100
  logging.info("done. new size %s. (%.0f reduction)", new_size_human_readable,
               reduction_ratio)


def sql_insert_dict(c, table: str, data: dict, ignore_existing: bool = False,
                    replace_existing: bool = False) -> None:
  """
  Insert a dict of key value pairs into an SQL table.

  Uses the key names as column names, as the values as column values.

  Parameters
  ----------
  c : sqlite3.Cursor
      Database cursor.
  table : str
      Destination table.
  data : dict
      Key value pairs.
  ignore_existing : bool, optional
      Ignore existing entries.
  replace_existing : bool, optional
      Replace existing entries.
  """
  or_ignore = "OR IGNORE" if ignore_existing else ""
  or_replace = "OR REPLACE" if replace_existing else ""
  cols = ','.join(sorted(data.keys()))
  vals = ','.join(['?'] * len(data))

  cmd = ("INSERT {or_ignore} {or_replace} INTO {table}({cols}) VALUES({"
         "vals})".format(**vars()))

  c.execute(cmd, tuple([data[v] for v in sorted(data.keys())]))


_sql_rm_chars = re.compile(r'[\(\)]')
_sql_sub_chars = re.compile(r'-')


def escape_sql_key(key: str) -> str:
  """
  Escape SQL key.

  Parameters
  ----------
  key : str
      SQL key.

  Returns
  -------
  str
      Escaped key.
  """
  return re.sub(_sql_sub_chars, '_',
                re.sub(_sql_rm_chars, '', '_'.join(key.split(' '))))


def kid_to_path(id: str) -> str:
  """
  Sanitize ID.

  Parameters
  ----------
  id : str
      ID.

  Returns
  -------
  str
      Path.
  """
  return re.sub('[/:\. ]+', '-', id)


def _dump_db(db, out_path: str, gh: bool = False, fileid: bool = False,
             reverse: bool = False, input_samples: bool = False,
             status: int = 0, eof: bool = False, dir: bool = False) -> None:
  """
  Dump database contents.

  Parameters
  ----------
  db : slite3.Connection
      Dataset.
  out_path : str
      Path to output.
  gh : bool, optional
      Dataset is GitHub.
  fileid : bool, optional
      Include file IDs.
  reverse : bool, optional
      Reverse ordering of output.
  input_samples : bool, optional
      If True, use un-preprocessed files.
  status : int, optional
      Filter preprocess status.
  eof : bool, optional
      Include EOF separators.
  dir : bool, optional
      Write output to directory.
  """
  logging.info('writing corpus %s ...', out_path)

  order = 'ASC' if reverse else 'DESC'

  c = db.cursor()

  # Query components
  table = 'ContentFiles' if input_samples else 'PreprocessedFiles'
  select = 'SELECT {}.id,{}.contents'.format(table, table, table)

  if input_samples:
    qualifier = ''
  else:
    qualifier = 'WHERE {}.status={}'.format(table, status)

  if gh:
    table += (' LEFT JOIN ContentMeta ON {}.id=ContentMeta.id'
              ' LEFT JOIN Repositories ON '
              'ContentMeta.repo_url=Repositories.url'.format(table))
    orderby = 'Repositories.stars'
  else:
    orderby = 'LC_col(contents)'

  query = (
    '{select} FROM {table} {qualifier} ORDER BY {orderby} {order}'.format(
      select=select, table=table, qualifier=qualifier, orderby=orderby,
      order=order))

  c.execute(query)
  rows = c.fetchall()

  if dir:
    logging.info('writing to directory %s/', out_path)
    if not os.path.exists(out_path):
      os.makedirs(out_path)
    for row in rows:
      id, contents = row
      path = os.path.join(out_path, kid_to_path(id) + '.cl')
      with open(path, 'w') as out:
        out.write(contents)
  else:
    logging.info('writing file %s', out_path)
    with open(out_path, 'wb') as out:
      for row in rows:
        id, contents = row
        if fileid:  # Print file ID
          out.write('/* ID: {} */\n\n'.format(id).encode('utf-8'))
        out.write(contents.encode('utf-8'))
        if eof:  # Print EOF token
          out.write('\n/* EOF */\n\n'.encode('utf-8'))
        else:
          out.write('\n\n'.encode('utf-8'))


def dump_db(db_path: str, out_path: str, **kwargs) -> None:
  """
  Dump database contents.

  Parameters
  ----------
  db_path : str
      Dataset.
  out_path : str
      Corpus path.
  **kwargs : dict
      Additional arguments to _dump_db().
  """
  db = connect(db_path)

  # auto-detect whether it's a GitHub repo
  kwargs['gh'] = is_github(db)

  _dump_db(db, out_path, **kwargs)


def get_all_sampler_datasets(all_clgen_versions: bool = True) -> list:
  # TODO(cec): CLgen will no longer use a global cache, so there is no concept
  # of "all" sampler datasets.
  if all_clgen_versions:
    versiondirs = fs.ls(fs.path("~/.cache/clgen"), abspaths=True)
  else:
    versiondirs = [fs.path("~/.cache/clgen")]

  versiondirs = [v for v in versiondirs if fs.isdir(v, "sampler")]

  datasets = []
  for versiondir in versiondirs:
    for samplerdir in fs.ls(fs.path(versiondir, "sampler"), abspaths=True):
      inpath = fs.path(samplerdir, "kernels.db")
      if fs.isfile(inpath):
        datasets.append(inpath)

  return datasets


def merge(outpath, inpaths=None):
  """
  Merge kernel datasets.
  """
  if not fs.isfile(outpath):
    create_db(outpath)
    logging.info("created %s", outpath)

  db = connect(outpath)

  if not inpaths:
    inpaths = get_all_sampler_datasets()

  for inpath in inpaths:
    logging.info("merging from %s", inpath)
    c = db.cursor()
    c.execute("ATTACH '{}' AS rhs".format(inpath))
    c.execute("INSERT OR IGNORE INTO ContentFiles "
              "SELECT * FROM rhs.ContentFiles")
    c.execute("INSERT OR IGNORE INTO PreprocessedFiles "
              "SELECT * FROM rhs.PreprocessedFiles")
    db.commit()
    c.execute("DETACH rhs")
    c.close()


def HasContentMetaTable(db_path: pathlib.Path) -> bool:
  """Check if database has a ContentMeta table.

  Args:
    db_path: Path to the contentfiles database.

  Returns:
    True if ContentMeta table exists, else False.
  """
  db = sqlite3.connect(str(db_path))
  c = db.cursor()
  c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='ContentMeta';")
  meta_table = c.fetchone()
  c.close()
  db.close()
  return True if meta_table else False

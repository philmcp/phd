"""Preprocess files within a dataset."""
import importlib
import pathlib
import typing

from absl import flags

from datasets.github.scrape_repos.preprocessors import public


FLAGS = flags.FLAGS


def GetPreprocessorFunction(name: str) -> public.PreprocessorFunction:
  """Lookup a dataset preprocess function by name.

  A dataset preprocessor is a function which two arguments: a root directory,
  and a relative path to a file within that directory. The name is the fully
  qualified name of the python function which implements it, in the form
  <module>:<name>. For example, the name
  'datasets.github.scrape_repos.inliners:CxxHeaders' will return the
  function 'CxxHeaders' in the module 'datasets.github.scrape_repos.inliners'.

  Args:
    name: The name of the preprocessor to get.

  Returns:
    The python preprocessor function.

  Raises:
    ValueError: If the requested name cannot be found or is not a
      @dataset_preprocessor decorated function.
  """
  components = name.split(':')
  if len(components) != 2:
    raise ValueError(f'Invalid preprocessor name {name}')
  module_name, function_name = components
  try:
    module = importlib.import_module(module_name)
    function_ = getattr(module, function_name)
  except (ModuleNotFoundError, AttributeError):
    raise ValueError(f'Preprocessor {name} not found.')
  if not function_.__dict__.get('is_dataset_preprocessor'):
    raise ValueError(
        f'Preprocessor {name} not decorated with @dataset_preprocessor')
  return function_


def Preprocess(import_root: pathlib.Path, file_relpath: str,
               preprocessors: typing.List[str]) -> str:
  """Preprocess a text using the given preprocessor pipeline.

  If preprocessing succeeds, the preprocessed text is returned. If preprocessing
  fails (in an expected way, for example by trying to compile incorrect code),
  a BadCodeException is raised. Any other error leads to an InternalError.


  Args:
    text: The input to be preprocessed.
    preprocessors: The list of preprocessor functions to run. These will be
      passed to GetPreprocessorFunction() to resolve the python implementations.

  Returns:
    Preprocessed source input as a string.

  Raises:
    FileNotFoundError: If the file does not exist.
    ValueError: If the requested preprocessors cannot be loaded.
    BadCodeException: If one of the preprocessors rejects the input.
    InternalException: In case of some other error.
  """
  path = import_root / file_relpath
  if not path.is_file():
    raise FileNotFoundError(f"File not found: {path}")

  with open(path) as f:
    text = f.read()

  preprocessor_functions = [GetPreprocessorFunction(p) for p in preprocessors]
  for preprocessor in preprocessor_functions:
    text = preprocessor(import_root, file_relpath, text)
  return text
"""Unit tests for //deeplearning/clgen/models/data_generators.py."""
import sys

import pytest
from absl import app

from deeplearning.clgen import errors
from deeplearning.clgen.models import data_generators


class CorpusMock(object):

  def __init__(self, corpus_length: int = 100):
    self.corpus_len = corpus_length

  def GetTrainingData(self, *args, **kwargs):
    return ['a'] * self.corpus_len


def test_DataGeneratorBase_sequence_length(abc_model_config):
  """Test that sequence length derives from TrainingOptions.sequence_length."""
  opt = abc_model_config.training
  opt.sequence_length = 10
  dg = data_generators.DataGeneratorBase(
      CorpusMock(corpus_length=100), opt)
  assert dg.sequence_length == 10


def test_DataGeneratorBase_sequence_length_too_large(abc_model_config):
  """Test that sequence length derives from TrainingOptions.sequence_length."""
  opt = abc_model_config.training
  opt.sequence_length = 50
  with pytest.raises(errors.UserError) as e_info:
    data_generators.DataGeneratorBase(CorpusMock(corpus_length=10), opt)
  assert ("Requested training.sequence_length (50) is larger than the corpus "
          "(10). Reduce the sequence length to <= 9.") == str(e_info.value)


def test_DataGeneratorBase_batch_size(abc_model_config):
  """Test that batch size is derived from TrainingOptions.batch_size."""
  opt = abc_model_config.training
  opt.batch_size = 10
  dg = data_generators.DataGeneratorBase(CorpusMock(corpus_length=100), opt)
  assert dg.batch_size == 10


def test_DataGeneratorBase_batch_size_too_large(abc_model_config):
  """Test that batch size is reduced when larger than corpus."""
  opt = abc_model_config.training
  opt.batch_size = 50
  opt.sequence_length = 5
  dg = data_generators.DataGeneratorBase(CorpusMock(corpus_length=10), opt)
  assert dg.batch_size == 4


def main(argv):
  """Main entry point."""
  if len(argv) > 1:
    raise app.UsageError('Unrecognized command line flags.')
  sys.exit(pytest.main([__file__, '-v']))


if __name__ == '__main__':
  app.run(main)
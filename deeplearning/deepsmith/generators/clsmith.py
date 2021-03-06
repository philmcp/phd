"""A CLSmith program generator."""
import math
import typing

from absl import app
from absl import flags
from absl import logging

from compilers.clsmith import clsmith
from deeplearning.deepsmith import services
from deeplearning.deepsmith.generators import generator
from deeplearning.deepsmith.proto import deepsmith_pb2
from deeplearning.deepsmith.proto import generator_pb2
from deeplearning.deepsmith.proto import generator_pb2_grpc
from deeplearning.deepsmith.proto import service_pb2
from labm8 import labdate


FLAGS = flags.FLAGS


def ConfigToGenerator(
    config: generator_pb2.ClsmithGenerator) -> deepsmith_pb2.Generator:
  """Convert a config proto to a DeepSmith generator proto."""
  g = deepsmith_pb2.Generator()
  g.name = 'clsmith'
  g.opts['opts'] = ' '.join(config.opt)
  return g


class ClsmithGenerator(generator.GeneratorServiceBase,
                       generator_pb2_grpc.GeneratorServiceServicer):

  def __init__(self, config: generator_pb2.ClgenGenerator):
    super(ClsmithGenerator, self).__init__(config)
    self.toolchain = 'opencl'
    self.generator = ConfigToGenerator(self.config)
    if not self.config.testcase_skeleton:
      raise ValueError('No testcase skeletons provided')
    for skeleton in self.config.testcase_skeleton:
      skeleton.generator.CopyFrom(self.generator)

  def GenerateTestcases(self, request: generator_pb2.GenerateTestcasesRequest,
                        context) -> generator_pb2.GenerateTestcasesResponse:
    del context
    num_programs = int(math.ceil(
        request.num_testcases / len(self.config.testcase_skeleton)))
    response = services.BuildDefaultResponse(
        generator_pb2.GenerateTestcasesResponse)
    try:
      for i in range(num_programs):
        response.testcases.extend(
            self.SourceToTestcases(*self.GenerateOneSource()))
        logging.info('Generated file %d.', i + 1)
    except clsmith.CLSmithError as e:
      response.status.returncode = service_pb2.ServiceStatus.ERROR
      response.status.error_message = str(e)
    return response

  def GenerateOneSource(self) -> typing.Tuple[str, int, int]:
    """Generate and return a single CLSmith program.

    Returns:
      A tuple of the source code as a string, the generation time, and the start
      time.
    """
    start_epoch_ms_utc = labdate.MillisecondsTimestamp()
    src = clsmith.Exec(*list(self.config.opt))
    wall_time_ms = labdate.MillisecondsTimestamp() - start_epoch_ms_utc
    return src, wall_time_ms, start_epoch_ms_utc

  def SourceToTestcases(self, src: str,
                        wall_time_ms: int,
                        start_epoch_ms_utc: int) -> typing.List[
    deepsmith_pb2.Testcase]:
    """Make testcases from a CLSmith generated source."""
    testcases = []
    for skeleton in self.config.testcase_skeleton:
      t = deepsmith_pb2.Testcase()
      t.CopyFrom(skeleton)
      p = t.profiling_events.add()
      p.type = 'generation'
      p.duration_ms = wall_time_ms
      p.event_start_epoch_ms = start_epoch_ms_utc
      t.inputs['src'] = src
      testcases.append(t)
    return testcases


if __name__ == '__main__':
  app.run(ClsmithGenerator.Main(generator_pb2.ClsmithGenerator))

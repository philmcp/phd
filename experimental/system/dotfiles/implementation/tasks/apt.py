from experimental.system.dotfiles.implementation.host import CheckShellCommand, \
  ShellCommand


class Apt(object):
  """ debian package manager """

  def install_package(self, package):
    """ install a package using apt-get, return True if installed """
    if not CheckShellCommand(
        "dpkg -s '{package}' &>/dev/null".format(package=package)):
      ShellCommand(
          "sudo apt-get install -y '{package}'".format(package=package))
      return True

  def update(self):
    """ update package information """
    ShellCommand("sudo apt-get update")

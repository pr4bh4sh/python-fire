# Copyright (C) 2018 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility for producing help strings for use in Fire CLIs.

Can produce help strings suitable for display in Fire CLIs for any type of
Python object, module, class, or function.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import inspect

from fire import completion
from fire import docstrings
from fire import inspectutils
from fire import value_types


def _NormalizeField(field):
  """Takes a field name and turns it into a human readable name for display.

  Args:
    field: The field name, used to index into the inspection dict.
  Returns:
    The human readable name, suitable for display in a help string.
  """
  if field == 'type_name':
    field = 'type'
  return (field[0].upper() + field[1:]).replace('_', ' ')


def _DisplayValue(info, field, padding):
  """Gets the value of field from the dict info for display.

  Args:
    info: The dict with information about the component.
    field: The field to access for display.
    padding: Number of spaces to indent text to line up with first-line text.
  Returns:
    The value of the field for display, or None if no value should be displayed.
  """
  value = info.get(field)

  if value is None:
    return None

  skip_doc_types = ('dict', 'list', 'unicode', 'int', 'float', 'bool')

  if field == 'docstring':
    if info.get('type_name') in skip_doc_types:
      # Don't show the boring default docstrings for these types.
      return None
    elif value == '<no docstring>':
      return None

  elif field == 'usage':
    lines = []
    for index, line in enumerate(value.split('\n')):
      if index > 0:
        line = ' ' * padding + line
      lines.append(line)
    return '\n'.join(lines)

  return value


def _GetFields(trace=None):
  """Returns the field names to include in the help text for a component."""
  del trace  # Unused.
  return [
      'type_name',
      'string_form',
      'file',
      'line',
      'docstring',
      'init_docstring',
      'class_docstring',
      'call_docstring',
      'length',
      'usage',
  ]


def HelpString(component, trace=None, verbose=False):
  """Returns a help string for a supplied component.

  The component can be any Python class, object, function, module, etc.

  Args:
    component: The component to determine the help string for.
    trace: The Fire trace leading to this component.
    verbose: Whether to include private members in the help string.
  Returns:
    String suitable for display giving information about the component.
  """
  info = inspectutils.Info(component)
  # TODO(dbieber): Stop using UsageString in favor of UsageText.
  info['usage'] = UsageString(component, trace, verbose)
  info['docstring_info'] = docstrings.parse(info['docstring'])

  is_error_screen = False
  if trace:
    is_error_screen = trace.HasError()

  if is_error_screen:
    # TODO(dbieber): Call UsageText instead of CommonHelpText once ready.
    return _CommonHelpText(info, trace)
  else:
    return _HelpText(info, trace)


def _CommonHelpText(info, trace=None):
  """Returns help text.

  This was a copy of previous HelpString function and will be removed once the
  correct text formatters are implemented.

  Args:
    info: The IR object containing metadata of an object.
    trace: The Fire trace object containing all metadata of current execution.
  Returns:
    String suitable for display giving information about the component.
  """
  # TODO(joejoevictor): Currently this is just a copy of existing HelpString
  # method. We will reimplement this further in later CLs.
  fields = _GetFields(trace)

  try:
    max_size = max(
        len(_NormalizeField(field)) + 1
        for field in fields
        if field in info and info[field])
    format_string = '{{field:{max_size}s}} {{value}}'.format(max_size=max_size)
  except ValueError:
    return ''

  lines = []
  for field in fields:
    value = _DisplayValue(info, field, padding=max_size + 1)
    if value:
      if lines and field == 'usage':
        lines.append('')  # Ensure a blank line before usage.

      lines.append(format_string.format(
          field=_NormalizeField(field) + ':',
          value=value,
      ))
  return '\n'.join(lines)


def UsageText(component, trace=None, verbose=False):
  if inspect.isroutine(component) or inspect.isclass(component):
    return UsageTextForFunction(component, trace)
  else:
    return UsageTextForObject(component, trace, verbose)


def UsageTextForFunction(component, trace=None):
  """Returns usage text for function objects.

  Args:
    component: The component to determine the usage text for.
    trace: The Fire trace object containing all metadata of current execution.

  Returns:
    String suitable for display in error screen.
  """

  output_template = """Usage: {current_command} {args_and_flags}
{availability_lines}
For detailed information on this command, run:
{current_command}{hyphen_hyphen} --help
"""

  if trace:
    command = trace.GetCommand()
    is_help_an_arg = trace.NeedsSeparatingHyphenHyphen()
  else:
    command = None
    is_help_an_arg = False

  if not command:
    command = ''

  spec = inspectutils.GetFullArgSpec(component)
  args = spec.args

  if spec.defaults is None:
    num_defaults = 0
  else:
    num_defaults = len(spec.defaults)
  args_with_no_defaults = args[:len(args) - num_defaults]
  args_with_defaults = args[len(args) - num_defaults:]
  flags = args_with_defaults + spec.kwonlyargs

  items = [arg.upper() for arg in args_with_no_defaults]
  if flags:
    items.append('<flags>')
    availability_lines = (
        '\nAvailable flags: '
        + ' | '.join('--' + flag for flag in flags) + '\n')
  else:
    availability_lines = ''
  args_and_flags = ' '.join(items)

  hyphen_hyphen = ' --' if is_help_an_arg else ''

  return output_template.format(
      current_command=command,
      args_and_flags=args_and_flags,
      availability_lines=availability_lines,
      hyphen_hyphen=hyphen_hyphen)


def UsageTextForObject(component, trace=None, verbose=False):
  """Returns help text for usage screen for objects.

  Construct help text for usage screen to inform the user about error occurred
  and correct syntax for invoking the object.

  Args:
    component: The component to determine the usage text for.
    trace: The Fire trace object containing all metadata of current execution.
    verbose: Whether to include private members in the usage text.
  Returns:
    String suitable for display in error screen.
  """
  output_template = """Usage: {current_command} <{possible_actions}>
{availability_lines}

For detailed information on this command, run:
{current_command} --help
"""
  if trace:
    command = trace.GetCommand()
  else:
    command = None

  if not command:
    command = ''

  groups = []
  commands = []
  values = []

  members = completion._Members(component, verbose)  # pylint: disable=protected-access
  for member_name, member in members:
    if value_types.IsGroup(member):
      groups.append(member_name)
    if value_types.IsCommand(member):
      commands.append(member_name)
    if value_types.IsValue(member):
      values.append(member_name)

  possible_actions = []
  availability_lines = []
  availability_lint_format = '{header:20s}{choices}'
  if groups:
    possible_actions.append('groups')
    groups_string = ' | '.join(groups)
    groups_text = availability_lint_format.format(
        header='available groups:',
        choices=groups_string)
    availability_lines.append(groups_text)
  if commands:
    possible_actions.append('commands')
    commands_string = ' | '.join(commands)
    commands_text = availability_lint_format.format(
        header='available commands:',
        choices=commands_string)
    availability_lines.append(commands_text)
  if values:
    possible_actions.append('values')
    values_string = ' | '.join(values)
    values_text = availability_lint_format.format(
        header='available values:',
        choices=values_string)
    availability_lines.append(values_text)
  possible_actions_string = '|'.join(possible_actions)
  availability_lines_string = '\n'.join(availability_lines)

  return output_template.format(
      current_command=command,
      possible_actions=possible_actions_string,
      availability_lines=availability_lines_string)


def _HelpText(info, trace=None):
  """Returns help text for extensive help screen.

  Construct help text for help screen when user explicitly requesting help by
  having -h, --help in the command sequence.

  Args:
    info: The IR object containing metadata of an object.
    trace: The Fire trace object containing all metadata of current execution.
  Returns:
    String suitable for display in extensive help screen.
  """

  # TODO(joejoevictor): Implement real help text construction.
  return _CommonHelpText(info, trace)


def _UsageStringFromFullArgSpec(command, spec):
  """Get a usage string from the FullArgSpec for the given command.

  The strings look like:
  command --arg ARG [--opt OPT] [VAR ...] [--KWARGS ...]

  Args:
    command: The command leading up to the function.
    spec: a FullArgSpec object describing the function.
  Returns:
    The usage string for the function.
  """
  num_required_args = len(spec.args) - len(spec.defaults)

  help_flags = []
  help_positional = []
  for index, arg in enumerate(spec.args):
    flag = arg.replace('_', '-')
    if index < num_required_args:
      help_flags.append('--{flag} {value}'.format(flag=flag, value=arg.upper()))
      help_positional.append('{value}'.format(value=arg.upper()))
    else:
      help_flags.append('[--{flag} {value}]'.format(
          flag=flag, value=arg.upper()))
      help_positional.append('[{value}]'.format(value=arg.upper()))

  if spec.varargs:
    help_flags.append('[{var} ...]'.format(var=spec.varargs.upper()))
    help_positional.append('[{var} ...]'.format(var=spec.varargs.upper()))

  for arg in spec.kwonlyargs:
    if arg in spec.kwonlydefaults:
      arg_str = '[--{flag} {value}]'.format(flag=arg, value=arg.upper())
    else:
      arg_str = '--{flag} {value}'.format(flag=arg, value=arg.upper())
    help_flags.append(arg_str)
    help_positional.append(arg_str)

  if spec.varkw:
    help_flags.append('[--{kwarg} ...]'.format(kwarg=spec.varkw.upper()))
    help_positional.append('[--{kwarg} ...]'.format(kwarg=spec.varkw.upper()))

  commands_flags = command + ' '.join(help_flags)
  commands_positional = command + ' '.join(help_positional)
  commands = [commands_positional]

  if commands_flags != commands_positional:
    commands.append(commands_flags)

  return '\n'.join(commands)


def UsageString(component, trace=None, verbose=False):
  """Returns a string showing how to use the component as a Fire command."""
  if trace:
    command = trace.GetCommand()
  else:
    command = None

  if command:
    command += ' '
  else:
    command = ''

  if inspect.isroutine(component) or inspect.isclass(component):
    spec = inspectutils.GetFullArgSpec(component)
    return _UsageStringFromFullArgSpec(command, spec)

  if isinstance(component, (list, tuple)):
    length = len(component)
    if length == 0:
      return command
    if length == 1:
      return command + '[0]'
    return command + '[0..{cap}]'.format(cap=length - 1)

  completions = completion.Completions(component, verbose)
  if command:
    completions = [''] + completions
  return '\n'.join(command + end for end in completions)

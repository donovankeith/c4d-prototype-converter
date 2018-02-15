# Copyright (c) 2018 Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import division, print_function
import c4d
import collections
import errno
import os
import re
import sys
import weakref


# ============================================================================
# Helpers
# ============================================================================

class DialogOpenerCommand(c4d.plugins.CommandData):
  """
  Command plugin that opens a dialog.
  """

  def __init__(self, dlg_factory, dlgtype=c4d.DLG_TYPE_ASYNC, *open_args, **open_kwargs):
    super(DialogOpenerCommand, self).__init__()
    self.dlg_factory = dlg_factory
    self.open_args = (dlgtype,) + open_args
    self.open_kwargs = open_kwargs
    self.dlg = None

  def Execute(self, doc):
    if not self.dlg: self.dlg = self.dlg_factory()
    self.dlg.Open(*self.open_args, **self.open_kwargs)
    return True

  def Register(self, plugin_id, name, info=0, icon=None, help=''):
    return c4d.plugins.RegisterCommandPlugin(
      plugin_id, name, info, icon, help, self)


class BaseDialog(c4d.gui.GeDialog):
  """
  A new base class for Cinema 4D dialogs that provides a bunch of useful
  methods for managing widgets.
  """

  def __init__(self):
    super(BaseDialog, self).__init__()
    self.__widgets = {}
    self.__reverse_cache = {}
    self.__idcounter = 9000000

  def AllocId(self):
    """
    Allocates a new ID. Used for widgets that require more than one real widget.
    """

    result = self.__idcounter
    self.__idcounter += 1
    return result

  def ReverseMapId(self, param_id):
    """
    Reverse-maps a real parameter ID to the ID of a virtual widget. If there
    is no virtual widget that allocated *param_id*, returns (None, param_id).
    If a widget has been found that uses *param_id*, returns (name, widget_id).
    """

    try:
      return self.__reverse_cache[param_id]
    except KeyError:
      result = None
      for widget_id, widget in self.__widgets.items():
        for key in widget:
          if key.startswith('id.') and widget[key] == param_id:
            result = key[3:], widget_id
            break
        if result: break
      if not result:
        result = (None, param_id)
      self.__reverse_cache[param_id] = result
      return result

  def ForwardMapId(self, virtual_id):
    """
    A generator for IDs that of the virtual parameter *virtual_id* or just
    the *virtual_id* if it does not correspond to a virtual parameter.
    """

    widget = self.__widgets.get(virtual_id, {})
    has_id = False
    for key in widget:
      if key.startswith('id.'):
        yield widget[key]
        has_id = True
    if not has_id:
      yield virtual_id

  def GetColor(self, colorid):
    c = self.GetColorRGB(colorid)
    return c4d.Vector(c['r'] / 255., c['g'] / 255., c['b'] / 255.)

  def SetColor(self, param_id, colorid, color=None):
    if color is None:
      color = self.GetColor(colorid)
    for real_id in self.ForwardMapId(param_id):
      self.SetDefaultColor(real_id, colorid, color)

  def SendCommand(self, param_id, bc=None):
    if bc is None:
      bc = c4d.BaseContainer()
    bc.SetId(c4d.BFM_ACTION)
    bc.SetInt32(c4d.BFM_ACTION_ID, param_id)
    return self.Message(bc, c4d.BaseContainer())

  def __FileSelectorCallback(self, widget, event):
    if event['type'] == 'command' and event['param'] == widget['id.button']:
      flags = {
        'load': c4d.FILESELECT_LOAD,
        'save': c4d.FILESELECT_SAVE,
        'directory': c4d.FILESELECT_DIRECTORY
      }[widget['fileselecttype']]
      path = c4d.storage.LoadDialog(flags=flags)
      if path:
        self.SetString(widget['id.string'], path)
        self.SendCommand(widget['id.string'])
      return True

  def AddFileSelector(self, param_id, flags, type='load'):
    if type not in ('load', 'save', 'directory'):
      raise ValueError('invalid type: {!r}'.format(type))
    widget = {
      'type': 'fileselector',
      'id.string': self.AllocId(),
      'id.button': self.AllocId(),
      'callback': self.__FileSelectorCallback,
      'fileselecttype': type
    }
    self.__widgets[param_id] = widget
    self.GroupBegin(0, flags, 2, 0)
    self.AddEditText(widget['id.string'], c4d.BFH_SCALEFIT | c4d.BFV_FIT)
    self.AddButton(widget['id.button'], c4d.BFH_CENTER | c4d.BFV_CENTER, name='...')
    self.GroupEnd()

  def GetFileSelectorString(self, param_id):
    return self.GetString(self.__widgets[param_id]['id.string'])

  def SetFileSelectorString(self, param_id, *args, **kwargs):
    self.SetString(self.__widgets[param_id]['id.string'], *args, **kwargs)

  def AddLinkBoxGui(self, param_id, flags, minw=0, minh=0, customdata=None):
    if customdata is None:
      customdata = c4d.BaseContainer()
    elif isinstance(customdata, dict):
      bc = c4d.BaseContainer()
      for key, value in customdata.items():
        bc[key] = value
      customdata = bc
    elif not isinstance(customdata, c4d.BaseContainer):
      raise TypeError('expected one of {NoneType,dict,c4d.BaseContainer}')
    widget = {
      'type': 'linkbox',
      'gui': self.AddCustomGui(param_id, c4d.CUSTOMGUI_LINKBOX, "", flags, minw, minh, customdata)
    }
    self.__widgets[param_id] = widget
    return widget['gui']

  def GetLink(self, param_id, doc=None, instance=0):
    return self.__widgets[param_id]['gui'].GetLink(doc, instance)

  def SetLink(self, param_id, obj):
    self.__widgets[param_id]['gui'].SetLink(obj)

  # @override
  def Command(self, param, bc):
    event = {'type': 'command', 'param': param, 'bc': bc}
    for widget in self.__widgets.values():
      callback = widget.get('callback')
      if callback:
        if callback(widget, event):
          return True
    return False


class HashableDescid(object):

  def __init__(self, descid):
    self.descid = descid

  def __hash__(self):
    return hash(tuple(
      (l.id, l.dtype, l.creator)
      for l in (
        self.descid[i] for i in xrange(self.descid.GetDepth())
      )
    ))

  def __eq__(self, other):
    if isinstance(other, HashableDescid):
      return other.descid == self.descid
    return False

  def __ne__(self, other):
    return not (self == other)


class NullableRef(object):
  """
  A weak-reference type that can represent #None.
  """

  def __init__(self, obj):
    self.set(obj)

  def __repr__(self):
    return '<NullableRef to {!r}>'.format(self())

  def __call__(self):
    if self._ref is not None:
      return self._ref()
    return None

  def set(self, obj):
    self._ref = weakref.ref(obj) if obj is not None else None


class Node(object):
  """
  Generic tree node type.
  """

  def __init__(self, data):
    self.data = data
    self.parent = NullableRef(None)
    self.children = []

  def __repr__(self):
    return '<Node data={!r}>'.format(self.data)

  def add_child(self, node):
    node.remove()
    node.parent.set(self)
    self.children.append(node)

  def remove(self):
    parent = self.parent()
    if parent:
      parent.children.remove(self)
    self.parent.set(None)

  def visit(self, func, with_root=True):
    if with_root:
      func(self)
    for child in self.children:
      child.visit(func)

  @property
  def depth(self):
    count = 0
    while True:
      self = self.parent()
      if not self: break
      count += 1
    return count


def makedirs(path, raise_on_exists=False):
  try:
    os.makedirs(path)
  except OSError as exc:
    if raise_on_exists or exc.errno != errno.EEXIST:
      raise


def path_parents(path):
  """
  A generator that returns *path* and all its parent directories.
  """

  yield path
  prev = None
  while True:
    path = os.path.dirname(path)
    if not path or prev == path: break  # Top of relative path or of filesystem
    yield path
    prev = path


def file_tree(files, parent=None, flat=False):
  """
  Produces a tree structure from a list of filenames. Returns a list of the
  root entries. If *flat* is set to #True, the returned list contains a flat
  version of all entries in the tree.
  """

  NodeData = collections.namedtuple('NodeData', 'path isdir')
  entries = {}

  files = (os.path.normpath(x) for x in files)
  if parent:
    files = (os.path.relpath(x, parent) for x in files)

  if flat:
    order = []
  for filename in files:
    parent_entry = None
    for path in reversed(list(path_parents(filename))):
      entry = entries.get(path)
      if not entry:
        entry = Node(NodeData(path, path!=filename))
        if parent_entry:
          parent_entry.add_child(entry)
        entries[path] = entry
        base = os.path.basename(path)
      parent_entry = entry
    if flat:
      order.append(entry)

  if flat:
    result = []
    for entry in order:
      index = len(result)
      while entry:
        if entry in result: break
        result.insert(index, entry)
        entry = entry.parent()
    return result
  else:
    return [x for x in entries.values() if not x.parent]


def userdata_tree(ud):
  """
  Builds a tree of userdata information. Returns a proxy root node that
  contains at least the main User Data group and eventually other root
  groups.
  """

  NodeData = collections.namedtuple('NodeData', 'descid bc')
  params = {}
  root = Node(None)

  # Create a node for every parameter.
  for descid, bc in ud:
    params[HashableDescid(descid)] = Node(NodeData(descid, bc))

  # The main userdata group is not described in the UserData container.
  descid = c4d.DescID(c4d.DescLevel(c4d.ID_USERDATA, c4d.DTYPE_SUBCONTAINER, 0))
  node = Node(NodeData(descid, c4d.BaseContainer()))
  params[HashableDescid(descid)] = node
  root.add_child(node)

  # Establish parent-child parameter relationships.
  for descid, bc in ud:
    node = params[HashableDescid(descid)]
    parent_id = bc[c4d.DESC_PARENTGROUP]
    try:
      parent = params[HashableDescid(parent_id)]
    except KeyError:
      root.add_child(node)
    else:
      parent.add_child(node)

  return root


# ============================================================================
# UserData to Description Resource Converter
# ============================================================================

class UserDataConverter(object):
  """
  This object holds the information on how the description resource will
  be generated.
  """

  class SymbolMap(object):

    def __init__(self, prefix):
      self.curr_id = 1000
      self.symbols = collections.OrderedDict()
      self.descid_to_symbol = {}
      self.prefix = prefix

    def get_unique_symbol(self, descid, name, value=None):
      base = self.prefix + re.sub('[^\w\d_]+', '_', name).upper().rstrip('_')
      index = 0
      while True:
        symbol = base + (str(index) if index != 0 else '')
        if symbol not in self.symbols: break
        index += 1
      if value is None:
        value = self.curr_id
        self.curr_id += 1
      self.symbols[symbol] = value
      if descid is not None:
        self.descid_to_symbol[HashableDescid(descid)] = symbol
      return symbol, value

  def __init__(self, link, plugin_name, plugin_id, resource_name,
               symbol_prefix, icon_file, directory, indent='  '):
    self.link = link
    self.plugin_name = plugin_name
    self.plugin_id = plugin_id
    self.resource_name = resource_name
    self.symbol_prefix = symbol_prefix
    self.icon_file = icon_file
    self.directory = directory
    self.indent = indent

  def plugin_type_info(self):
    if not self.link:
      return {}
    if self.link.CheckType(c4d.Obase):
      return {'resprefix': 'O', 'resbase': 'Obase', 'pluginclass': 'ObjectData'}
    if self.link.CheckType(c4d.Tbase):
      return {'resprefix': 'T', 'resbase': 'Tbase', 'pluginclass': 'TagData'}
    if self.link.CheckType(c4d.Xbase):
      return {'resprefix': 'X', 'resbase': 'Xbase', 'pluginclass': 'ShaderData'}
    if self.link.CheckType(c4d.Mbase):
      return {'resprefix': 'M', 'resbase': 'Mbase', 'pluginclass': None}
    return {}

  def autofill(self, default_plugin_name='My Plugin'):
    if not self.plugin_name:
      self.plugin_name = (self.link.GetName() if self.link else '')
    if not self.plugin_name:
      self.plugin_name = default_plugin_name
    if not self.resource_name:
      self.resource_name = re.sub('[^\w\d]+', '', self.plugin_name).lower()
      self.resource_name = self.plugin_type_info().get('resprefix', '') + self.resource_name
    if not self.symbol_prefix:
      self.symbol_prefix = re.sub('[^\w\d]+', '_', self.plugin_name).rstrip('_').upper() + '_'

  def files(self):
    f = lambda s: s.format(**sys._getframe(1).f_locals)
    j = os.path.join
    parent_dir = self.directory or self.plugin_name
    plugin_filename = re.sub('[^\w\d]+', '-', self.plugin_name).lower()
    plugin_type_info = self.plugin_type_info()
    result = {
      'directory': parent_dir,
      'c4d_symbols': j(parent_dir, 'res', 'c4d_symbols.h'),
      'header': j(parent_dir, 'res', 'description', f('{self.resource_name}.h')),
      'description': j(parent_dir, 'res', 'description', f('{self.resource_name}.res')),
      'strings_us': j(parent_dir, 'res', 'strings_us', 'description', f('{self.resource_name}.str'))
    }
    if plugin_type_info.get('pluginclass'):
      result['plugin'] = j(parent_dir, f('{plugin_filename}.pyp'))
    if self.icon_file:
      suffix = os.path.splitext(self.icon_file)[1]
      result['icon'] = j(parent_dir, 'res', 'icons', f('{self.plugin_name}{suffix}'))
    return result

  def create(self, overwrite=False):
    if not self.directory:
      raise RuntimeError('UserDataConverter.directory must be set')
    if not self.link:
      raise RuntimeError('UserDataConverter.link must be set')
    if self.icon_file and not os.path.isfile(self.icon_file):
      raise IOError('File "{}" does not exist'.format(self.icon_file))

    plugin_type_info = self.plugin_type_info()
    files = self.files()
    if not overwrite:
      for k in ('header', 'description', 'icon', 'strings_us'):
        v = files.get(k)
        if not v: continue
        if os.path.exists(v):
          raise IOError('File "{}" already exists'.format(v))

    makedirs(os.path.dirname(files['c4d_symbols']))
    if not os.path.isfile(files['c4d_symbols']):
      makedirs(os.path.dirname(files['c4d_symbols']))
      with open(files['c4d_symbols'], 'w') as fp:
        fp.write('#pragma once\nenum {\n};\n')

    ud = self.link.GetUserDataContainer()
    symbol_map = self.SymbolMap(self.symbol_prefix)
    ud_tree = userdata_tree(ud)
    ud_main_group = next((
      x for x in ud_tree.children
      if x.data.descid == c4d.DescID(c4d.ID_USERDATA)
    ))

    # Render the symbols to the description header. This will also
    # initialize our symbols_map.
    makedirs(os.path.dirname(files['header']))
    with open(files['header'], 'w') as fp:
      fp.write('#pragma once\nenum {\n')
      if self.plugin_id:
        fp.write(self.indent + '{self.resource_name} = {self.plugin_id},\n'.format(self=self))
      ud_tree.visit(lambda x: self.render_symbol(fp, x, symbol_map))
      fp.write('};\n')

    makedirs(os.path.dirname(files['description']))
    with open(files['description'], 'w') as fp:
      fp.write('CONTAINER {self.resource_name} {{\n'.format(self=self))
      for base, propgroup in [
          ('Obase', 'ID_OBJECTPROPERTIES'), ('Tbase', 'ID_TAGPROPERTIES'),
          ('Xbase', 'ID_SHADERPROPERTIES'), ('Mbase', 'ID_MATERIALPROPERTIES')]:
        if self.link.CheckType(getattr(c4d, base)):
          fp.write(self.indent + 'INCLUDE {base};\n'.format(base=base))
          break
      else:
        propgroup = None
      fp.write(self.indent + 'NAME {self.resource_name};\n'.format(self=self))
      if propgroup:
        fp.write(self.indent + 'GROUP {0} {{\n'.format(propgroup))
        for node in ud_main_group.children:
          self.render_parameter(fp, node, symbol_map, depth=2)
        fp.write(self.indent + '}\n')
      for node in ud_tree.children:
        if node.data.descid == c4d.DescID(c4d.ID_USERDATA): continue
        self.render_parameter(fp, node, symbol_map)
      fp.write('}\n')

    makedirs(os.path.dirname(files['strings_us']))
    with open(files['strings_us'], 'w') as fp:
      fp.write('STRINGTABLE {self.resource_name} {{\n'.format(self=self))
      fp.write('{self.indent}{self.resource_name} "{self.plugin_name}";\n'.format(self=self))
      ud_tree.visit(lambda x: self.render_symbol_string(fp, x, symbol_map))
      fp.write('}\n')

    if 'plugin' in files:
      makedirs(os.path.dirname(files['plugin']))
      with open(files['plugin'], 'w') as fp:
        plugin_class = re.sub('[^\w\d]+', '', self.plugin_name) + 'Data'
        fp.write('# Copyright (C) <year> <author>\n\n')
        fp.write('import c4d\n\n')
        # TODO: add code for Init() and registration process
        fp.write('class {}(c4d.plugins.{}):\n'.format(plugin_class, plugin_type_info['pluginclass']))
        fp.write(self.indent + 'pass\n\n')
        fp.write('def main():\n')
        fp.write(self.indent + 'pass\n\n')
        fp.write("if __name__ == '__main__':\n")
        fp.write(self.indent + 'main()\n')

    if self.icon_file:
      makedirs(os.path.dirname(files['icon']))
      shutil.copy(self.icon_file, files['icon'])

  def render_symbol(self, fp, node, symbol_map):
    if not node.data or node.data.descid == c4d.DescID(c4d.ID_USERDATA):
      return
    # Find a unique name for the symbol.
    name = node.data.bc[c4d.DESC_SHORT_NAME]
    if node.data.descid[-1].dtype == c4d.DTYPE_GROUP:
      name += '_GROUP'
    else:
      parent = node.parent()
      if parent.data:
        parent_name = parent.data.bc.GetString(c4d.DESC_NAME)
        if parent_name:
          name = parent_name + ' ' + name

    sym, value = symbol_map.get_unique_symbol(node.data.descid, name)
    fp.write(self.indent + '{} = {},\n'.format(sym, value))
    children = node.data.bc.GetContainerInstance(c4d.DESC_CYCLE)
    if children:
      for value, name in children:
        child_sym = symbol_map.get_unique_symbol(None, sym + '_' + name, value)[0]
        fp.write(self.indent * 2 + '{} = {},\n'.format(child_sym, value))

    return sym

  def render_parameter(self, fp, node, symbol_map, depth=1):
    bc = node.data.bc
    symbol = symbol_map.descid_to_symbol[HashableDescid(node.data.descid)]
    dtype = node.data.descid[-1].dtype
    if dtype == c4d.DTYPE_GROUP:
      fp.write(self.indent * depth + 'GROUP {} {{\n'.format(symbol))
      for child in node.children:
        self.render_parameter(fp, child, symbol_map, depth+1)
      fp.write(self.indent * depth + '}\n')
    else:
      typename = None
      props = []
      default = bc[c4d.DESC_DEFAULT]

      if bc[c4d.DESC_ANIMATE] == c4d.DESC_ANIMATE_OFF:
        props.append('ANIMATE OFF;')
      elif bc[c4d.DESC_ANIMATE] == c4d.DESC_ANIMATE_MIX:
        props.append('ANIMATE MIX;')

      if dtype == c4d.DTYPE_BOOL:
        typename = 'BOOL'
        if default is not None:
          props.append('DEFAULT 1;' if default else 'DEFAULT 0;')
      elif dtype == c4d.DTYPE_LONG:
        # TODO: Support for min/max values
        # TODO: Support for cycle/slider
        typename = 'LONG'
        if isinstance(default, int):
          props.append('DEFAULT {};'.format(int(default)))
      elif dtype == c4d.DTYPE_BUTTON:
        typename = 'BUTTON'
      elif dtype == c4d.DTYPE_COLOR:
        # TODO: Support for min/max values
        typename = 'COLOR'
        if isinstance(default, c4d.Vector):
          props.append('DEFAULT {0.x} {0.y} {0.z};'.format(default))
      elif dtype == c4d.DTYPE_FILENAME:
        typename = 'FILENAME'
      elif dtype == c4d.DTYPE_REAL:
        # TODO: Support for min/max values
        # TODO: Support for slider
        typename = 'REAL'
        if isinstance(default, float):
          props.append('DEFAULT {};'.format(default))
      elif dtype == c4d.DTYPE_GRADIENT:
        typename = 'GRADIENT'
      elif dtype == c4d.CUSTOMDATATYPE_INEXCLUDE:
        typename = 'IN_EXCLUDE'
      elif dtype == c4d.DTYPE_BASELISTLINK:
        typename = 'LINK'
        # TODO: Support for link field refuse/accept
      elif dtype == c4d.CUSTOMDATATYPE_SPLINE:
        typename = 'SPLINE'
      elif dtype == c4d.DTYPE_STRING:
        typename = 'STRING'
      elif dtype == c4d.DTYPE_TIME:
        # TODO: Support for min/max values
        typename = 'TIME'
      elif dtype == c4d.DTYPE_VECTOR:
        # TODO: Support for min/max values
        typename = 'VECTOR'
        if isinstance(default, c4d.Vector):
          props.append('DEFAULT {0.x} {0.y} {0.z};'.format(default))
      elif dtype == c4d.DTYPE_SEPARATOR:
        typename = 'SEPARATOR'
      else:
        print('Unhandled datatype:', dtype, '({})'.format(node.data.bc[c4d.DESC_NAME]))
        return

      fp.write(self.indent * depth + '{} {{ {}}}\n'.format(typename, ' '.join(props) + (' ' if props else '')))

  def render_symbol_string(self, fp, node, symbol_map):
    if not node.data or node.data.descid == c4d.DescID(c4d.ID_USERDATA):
      return
    # TODO: Escape special characters.
    symbol = symbol_map.descid_to_symbol[HashableDescid(node.data.descid)]
    fp.write(self.indent + '{} "{}";\n'.format(symbol, node.data.bc[c4d.DESC_NAME]))


class UserDataToDescriptionResourceConverterDialog(BaseDialog):
  """
  Implements the User Interface to convert an object's UserData to a
  Cinema 4D description resource.
  """

  ID_PLUGIN_NAME = 1000
  ID_ICON_FILE = 1001
  ID_RESOURCE_NAME = 1002
  ID_SYMBOL_PREFIX = 1003
  ID_DIRECTORY = 1004
  ID_LINK = 1005
  ID_CREATE = 1006
  ID_CANCEL = 1007
  ID_FILELIST_GROUP = 1008
  ID_OVERWRITE = 1009
  ID_PLUGIN_ID = 1010
  ID_INDENT = 1011

  INDENT_TAB = 0
  INDENT_2SPACE = 1
  INDENT_4SPACE = 2

  def get_converter(self):
    return UserDataConverter(
      link = self.GetLink(self.ID_LINK),
      plugin_name = self.GetString(self.ID_PLUGIN_NAME),
      plugin_id = self.GetString(self.ID_PLUGIN_ID),
      resource_name = self.GetString(self.ID_RESOURCE_NAME),
      symbol_prefix = self.GetString(self.ID_SYMBOL_PREFIX),
      icon_file = self.GetFileSelectorString(self.ID_ICON_FILE),
      directory = self.GetFileSelectorString(self.ID_DIRECTORY),
      indent = {self.INDENT_TAB: '\t', self.INDENT_2SPACE: '  ', self.INDENT_4SPACE: '    '}[self.GetInt32(self.ID_INDENT)]
    )

  def update_filelist(self):
    cnv = self.get_converter()
    cnv.autofill()
    files = cnv.files()

    parent = os.path.dirname(files.pop('directory'))
    files = sorted(files.values(), key=str.lower)

    self.LayoutFlushGroup(self.ID_FILELIST_GROUP)
    for entry in file_tree(files, parent=parent, flat=True):
      depth = 0
      parent = entry.parent()
      while parent:
        depth += 1
        parent = parent.parent()
      name = '  ' * depth + os.path.basename(entry.data.path)
      if entry.data.isdir:
        name += '/'
      self.AddStaticText(0, c4d.BFH_LEFT, name=name)
    self.LayoutChanged(self.ID_FILELIST_GROUP)

    self.SetString(self.ID_SYMBOL_PREFIX, cnv.symbol_prefix, False, c4d.EDITTEXT_HELPTEXT)
    self.SetString(self.ID_RESOURCE_NAME, cnv.resource_name, False, c4d.EDITTEXT_HELPTEXT)
    self.SetString(self.ID_PLUGIN_NAME, cnv.plugin_name, False, c4d.EDITTEXT_HELPTEXT)

  def update_create_enabling(self):
    # TODO: We could also update the default color of the parameters
    #        to visually indicate which parameters need to be filled.
    enabled = True
    ids = [self.ID_LINK, self.ID_DIRECTORY, self.ID_PLUGIN_ID]
    invalids = []
    if self.GetLink(self.ID_LINK) is None:
      invalids.append(self.ID_LINK)
      enabled = False
    if not self.GetFileSelectorString(self.ID_DIRECTORY):
      invalids.append(self.ID_DIRECTORY)
      enabled = False
    if not self.GetString(self.ID_PLUGIN_ID).isdigit():
      invalids.append(self.ID_PLUGIN_ID)
      enabled = False
    for param_id in ids:
      color = c4d.Vector(0.8, 0.1, 0.1) if param_id in invalids else None
      self.SetColor(param_id, c4d.COLOR_BG, color)
    self.Enable(self.ID_CREATE, enabled)

  def do_create(self):
    cnv = self.get_converter()
    cnv.autofill()
    if not cnv.link:
      c4d.gui.MessageDialog('No source object specified.')
      return
    if not cnv.directory:
      c4d.gui.MessageDialog('No output directory specified.')
      return
    try:
      cnv.create(overwrite=self.GetBool(self.ID_OVERWRITE))
    except IOError as exc:
      c4d.gui.MessageDialog(str(exc))

  # c4d.gui.GeDialog

  def CreateLayout(self):
    self.SetTitle('UserData to Description Resource (.res) Converter')
    self.GroupBorderSpace(6, 6, 6, 6)
    self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 0, 1)  # MAIN {
    self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, 1, 0)  # MAIN/LEFT {
    self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_FIT, 2, 0)  # MAIN/LEFT/PARAMS {
    self.AddStaticText(0, c4d.BFH_LEFT, name='Source *')
    self.AddLinkBoxGui(self.ID_LINK, c4d.BFH_SCALEFIT)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Plugin Name')
    self.AddEditText(self.ID_PLUGIN_NAME, c4d.BFH_SCALEFIT)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Plugin ID *')
    self.AddEditText(self.ID_PLUGIN_ID, c4d.BFH_LEFT, 100)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Resource Name')
    self.AddEditText(self.ID_RESOURCE_NAME, c4d.BFH_SCALEFIT)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Symbol Prefix')
    self.AddEditText(self.ID_SYMBOL_PREFIX, c4d.BFH_SCALEFIT)
    self.AddStaticText(0, c4d.BFH_LEFT, name='Icon')
    self.AddFileSelector(self.ID_ICON_FILE, c4d.BFH_SCALEFIT, type='load')
    self.AddStaticText(0, c4d.BFH_LEFT, name='Plugin Directory *')
    self.AddFileSelector(self.ID_DIRECTORY, c4d.BFH_SCALEFIT, type='directory')
    self.AddStaticText(0, c4d.BFH_LEFT, name='Indentation')
    self.AddComboBox(self.ID_INDENT, c4d.BFH_LEFT)
    self.AddChild(self.ID_INDENT, self.INDENT_TAB, 'Tab')
    self.AddChild(self.ID_INDENT, self.INDENT_2SPACE, '2 Spaces')
    self.AddChild(self.ID_INDENT, self.INDENT_4SPACE, '4 Spaces')
    self.AddCheckbox(self.ID_OVERWRITE, c4d.BFH_LEFT, 0, 0, name='Overwrite')
    self.GroupBegin(0, c4d.BFH_CENTER, 0, 1) # MAIN/LEFT/PARAMS/BUTTONS {
    self.AddButton(self.ID_CREATE, c4d.BFH_CENTER, name='Create')
    self.AddButton(self.ID_CANCEL, c4d.BFH_CENTER, name='Cancel')
    self.GroupEnd()  # } MAIN/LEFT/PARAMS/BUTTONS
    self.GroupEnd()  # } MAIN/LEFT/PARAMS
    self.GroupEnd()  # } MAIN/LEFT
    self.AddSeparatorV(0, c4d.BFV_SCALEFIT)
    self.GroupBegin(self.ID_FILELIST_GROUP, c4d.BFH_RIGHT | c4d.BFV_SCALEFIT, 1, 0) # MAIN/RIGHT {
    self.GroupBorderSpace(4, 4, 4, 4)
    self.GroupEnd()  # } MAIN/RIGHT
    self.GroupEnd()  # } MAIN
    self.update_filelist()
    self.update_create_enabling()
    return True

  def Command(self, param_id, bc):
    if BaseDialog.Command(self, param_id, bc):
      return True

    # The actual ID that we create a widget with. The real parameter ID and
    # the virtual ID are different for compound widgets such as the file
    # selector.
    virtual_id = self.ReverseMapId(param_id)[1]

    if virtual_id in (
      # Check if anything changed that would have an influence on the filelist.
        self.ID_PLUGIN_NAME, self.ID_RESOURCE_NAME, self.ID_DIRECTORY,
        self.ID_ICON_FILE, self.ID_LINK):
      self.update_filelist()

    if virtual_id in (self.ID_LINK, self.ID_DIRECTORY, self.ID_PLUGIN_ID):
      # Update the create button's enable state.
      self.update_create_enabling()

    if virtual_id == self.ID_CREATE:
      self.do_create()
      return True
    elif virtual_id == self.ID_CANCEL:
      self.Close()
      return True

    return True


def main():
  DialogOpenerCommand(UserDataToDescriptionResourceConverterDialog)\
    .Register(1040648, 'UserData to .res Converter')


if __name__ == '__main__':
  main()

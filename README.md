## Cinema 4D Prototype Converter

![](https://img.shields.io/badge/License-MIT-yellow.svg)

This plugin aids you in converting your Cinema 4D Python plugin prototype
to a plugin.

![](https://i.imgur.com/FCyghJm.png)

__To do__

* [ ] Support unit and step in REAL parameters
* [ ] Support Longitude/Latitude customgui for REAL parameters
* [ ] Support QuickTab & Radio customgui for LONG parameters
* [ ] Support for GROUP titlebar option

### Features

* Converts UserData to Cinema 4D description resource files
* Generates a Python plugin template file

### Planned Features

* Automatic conversion of Python Generators to ObjectData plugins (and alike) \*
* A tool to convert Scripts to CommandData plugins \*
* Reporting of possible errors during conversion (eg. referencing the
  variables `doc` or `op` in global functions without previously declaring
  them)
* Automatically replacing references to `op[c4d.ID_USERDATA, X]` syntax with
  the respectively automatically generated resource symbol

> \* Milestones set by the sponsors.

### Usage Instructions

#### Creating your First Resource

1. Create a Python Generator or Python Expression tag and add a custom UserData Interface.
2. Rename the object/tag to match the name you would like for your Plugin.
3. Select the object/tag.
4. Plugins > UserData to Description Resource (.res) Converter
5. If you selected an Object, it will be auto-linked in the `Source` field. If you selected a tag, you will need to manually drag it into the `Source` field.
6. Click on `Get Plugin ID` and generate a unique Plugin ID on [PluginCafe.com](https://developers.maxon.net/)
7. Copy & Paste your plugin id into the `Plugin ID` field.
8. Make any changes you would like to the `Resource Name` and `Symbol Prefix` field.
9. Click on the `...` button next to `Icon` to select a 32x32 pixel `.tif` icon for your plugin.
10. Adjust the `Plugin Directory` to place the generated plugin stub exactly where you want it. If you manually change this, be sure to create a folder with the same name as your plugin, or select the folder you would like to directly contain your plugin's `.pyp` file.
11. Prease `Create`
  * A File Browser window should open showing your newly created files.

#### Updating an Existing Resource

*Note: If you have made any changes to your parameter IDs or plugin `.res` files you probably should not use this feature. All of your resource files (and possibly even your plugin) will be overwritten. Be sure to use some form of Source Control (like [Git](https://github.com)) to ensure you can revert any potentially damaging changes.*

1. Select the object whose UserData you would like to update.
2. Plugins > User Data to Description Resource (.res) Convert.
  * The settings used for your last export of this object should be visible.
3. Change `Overwrite` from `Nothing` to `Resource Files` (Don't use `Everything` unless you're certain you know what you're doing).
4. Press `Create`

### Parameter Reference

* **Mode:**
* **Overwite:**
* **Indentation:**
* **Source *:**
* **Plugin Name:**
* **Plugin ID:**
* **Get Plugin ID:**
* **Resource Name:**
* **Symbol Prefix:**
* **Icon:**
* **Plugin Directory:**
* **Filelist:**

### Acknowledgements

This project is sponsored by [Maxon US](https://www.maxon.net/en-us/) and was created for [Cineversity.com](https://www.cineversity.com/)'s [CV-Toolbox](https://www.cineversity.com/vidplaytut/cv_toolbox)

- Programming and Design: [Niklas Rosenstein](https://www.niklasrosenstein.com/)
- Initial Concept and Design: [Donovan Keith](https://www.donovankeith.com)

---

<p align="center">Copyright &copy 2018 [Niklas Rosenstein](https://www.niklasrosenstein.com/)</p>

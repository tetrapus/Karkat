# Karkat

[![Build Status](https://travis-ci.org/tetrapus/Karkat.svg?branch=master)](https://travis-ci.org/tetrapus/Karkat)

Karkat is an extensible threaded python IRC bot, supporting dynamically loadable modules with interfaces at every level of abstraction.
The default set of plugins are (partially) documented at http://tetrapus.github.io/Karkat/docs.html

## Getting Started
1. Clone this repo.
2. Download dependencies with ''pip install -r requirements.txt``
3. Create a config file. A sample file (Sample.yaml) is provided. For convenience, a config generator mkconf.py is provided.
4. (Optional) Provide API keys. Create a file apikeys.conf in the config directory. Place your keys in the file (as yaml) in the format specified by the module.
5. Run karkat. Karkat is run via ``./karkat.py <config>``. Other options are available, see the full argspec via ./karkat.py -h.

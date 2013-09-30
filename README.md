# Karkat

Multithreaded python IRC socket bot.
Warning: This readme may be out of date. Karkat is undergoing thorough modifications to his plugin structure. The majority of former features are currently not ported to the new interface- this is reasonably easy to do, but I have not done so as I am cleaning them all up before re-adding them. Please be patient, and feel free to do it yourself.

## Getting Started
### Step 1: Download dependencies
If not already installed, the following packages must be installed:
- Docopt
- Requests
- PyYaml
- PyLast
 
Run ``sudo pip3 install docopt pyyaml requests pylast`` to install them.

### Step 2: Create server config
Create a config file. A sample file (Sample.yaml) is provided. For convenience, a config generator mkconf.py is provided.

### Step 3: Make api keys (optional)
Some modules require api keys. Create a file apikeys.conf in the working directory. Put your keys in there in the format specified by the module.

### Step 4: Run karkat
Karkat is run via ``./karkat.py <config>``. Some options are available, see the full argspec via ./karkat.py -h.

The information below this point is outdated.

## Files
The main file is ``karkat.py``. 

### threads.py 

This file contains the threads Karkat uses to operate. For every connection:
- There is 1 Printer thread and 1 Connection thread. Currently, the connection thread doesn't actually exist and is just stuck at the bottom of ``karkat.py``
- There is a dynamic-sized array of Caller threads, as dictated by the ``GP_CALLERS`` constant defined in ``karkat.py``

### irc.py
This file contains some helper functions to parse IRC messages. The callback class provides some decorators which affect the behaviour of how a callback is handled by the connection thread.

### text.py
This file contains some general text manipulation utilities. The design aesthetic of Karkat encourages short, multi-line output over information-dense, word-wrapped output.

### karkat.py
Good luck with this one.

Karkat reads from a socket connection to a server one line at a time and queues up the callbacks (in flist) to the caller threads with the arguments (words, line). callers[1] is the main worker thread and callers[0] is reserved for non-critical operations. Threadsafe callbacks can utilise all caller threads.

The printer class should be the only method for sending data to the server, to prevent threading issues. NOTE: ``karkat.py`` sets stdout to privmsg to the last used channel. 
Use printer.message(text, <channel, <method>>) to send a message to the server, or use the printer.buffer(channel) context manager to ensure multiple lines are not interleaved.

### features.py
All of the like, features are here. Currently they're just ``execfile()``'d after everything else is defined, so uh, be careful with that.

It also only is run if the -f flag is passed in for some reason.

## Defining a callback
The basic callback takes the arguments ``(words, line)`` where words is the line split by spaces, and line is the raw line from the server. Put the function in the corresponding entry in flist (where the keys are ``.lower()``'d ``word[1]``s).

### Decorators
- ``@Callback.threadsafe`` 
marks a function as threadsafe, which allows it to utilise the extra callables.
- ``@Callback.background``
marks a function as a background function (i.e low priority) which sticks it in an alternate caller.
- ``@Callback.msghandler``
changes the function signature of the callback to ``(Address, context, Message)``

Only works for callbacks of the form ":Address TYPE target :message" 
- ``@command(trigger, args=None or regexp, key=str.lower, help=None or str)``
changes the function signature of the callback to ``(message, [arg1, arg2...])``

Triggers the function only when the data matches the form ``[!@]trigger regexp``.

``trigger`` may be a string or a list of triggers. The key kwarg can be used to specify the key for what triggers are considered equivelant.

``args`` is a regular expression, with each group representing a new argument to give to the function. If None, no argument is matched.

``help`` is a string sent in place of the function's output if trigger matches, but args do not.

Only works for NOTICEs and PRIVMSGs

## Debugging mode
Debugging mode can be enabled with the ``-d [threshhold]`` option. This sends server input to stdout, as well as provides warnings when the dispatcher loop takes longer than 0.15 or ``threshhold`` seconds to complete.

Karkat also provides two interpretters, a bash one which may be used by sending ``$ COMMAND`` to the bot, or a python interpretter with access to the global namespace via ``>>> command`` or ``"""command"""``. Note: bolded text will be messaged back to the sending context.

## Features:
- A list of features is available at http://www.tetrap.us/karkat

Karkat's base system is thoroughly incomplete. Better documentation will be made available when the callback system is completed.

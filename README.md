# Karkat

Multithreaded python IRC socket bot.

## How to use Karkat
Create a config file. A sample file (Sample.yaml) is provided. Run Karkat as follows: ``python karkat.py <config>``
Some data files are not provided. Delete classes and entries in the callback registry (flist) as necessary until it works.

## Files
The main file is ``karkat.py``. Currently, this file sets up all the threads and callbacks, but the aim is to modularise this and replace it with a config.

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


## Features:
- A list of features is available at http://www.tetrap.us/karkat

Karkat's base system is thoroughly incomplete. Better documentation will be made available when the callback system is completed.

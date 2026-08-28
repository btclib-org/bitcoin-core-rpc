bitcoin_core_rpc module
=======================

One page for the package. The facade carries the design of the client
and the reasoning behind each refusal, and no member list of its own:
``automodule`` without ``:members:`` renders that docstring alone,
because a constant this facade only forwards through ``__getattr__``
has its attribute docstring in the module that defines it and nowhere
else, and ``autodoc`` reads a module's data members from that module's
own source. Every name in ``__all__`` is therefore documented once,
under whichever of the four defines it.

.. automodule:: bitcoin_core_rpc

.. automodule:: bitcoin_core_rpc.errors
   :members:
   :show-inheritance:

.. automodule:: bitcoin_core_rpc.chains
   :members:
   :show-inheritance:

.. automodule:: bitcoin_core_rpc.transport
   :members:
   :show-inheritance:

.. automodule:: bitcoin_core_rpc.client
   :members:
   :show-inheritance:

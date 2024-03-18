# ClassAccessorFunc Type Generator

This was made as a temporary solution to providing gamemode classes with proper type support
on their accessor functions with [lua-language-server](https://github.com/LuaLS/lua-language-server).

Eventually, I'll finish the proper GBuild using the [Loretta](https://github.com/LorettaDevs/Loretta) lua parser, however currently we're not even using an AST representation. Instead this literally parses the file line by line to find matching call signatures.

## Meta type files.

Specifically, this generates meta files that should be placed somewhere within the target workspace.
Alternatively, all meta files can be kept together and loaded as a `Lua.workspace.library`.

## Todo

Make this into a Github action.
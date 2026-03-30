cmake_minimum_required(VERSION 3.16)
project(StorageEngine CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)   # generates compile_commands.json

add_library(storage_engine STATIC
    src/disk_mgr.cpp
)

target_include_directories(storage_engine PUBLIC src)

import sys
from config import init as config_init
from server import build as build_server
from client import build as build_client
from shared import build as build_shared
from luau.roblox.rojo import build_sourcemap

INIT_TAG = "init"
BUILD_TAG = "build"

def main():
	assert len(sys.argv) > 1, "no arguments provided"
	if sys.argv[1] == INIT_TAG:
		config_init()
	elif sys.argv[1] == BUILD_TAG:
		build_shared()
		build_client()
		build_server()
		build_sourcemap()

main()
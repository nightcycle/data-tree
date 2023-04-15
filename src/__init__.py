import sys
from src.config import init as config_init
from src.server import build as build_server
from src.client import build as build_client

INIT_TAG = "init"
BUILD_TAG = "build"

def main():
	assert len(sys.argv) > 1, "no arguments provided"
	if sys.argv[1] == INIT_TAG:
		config_init()
	elif sys.argv[1] == BUILD_TAG:
		build_client()
		build_server()

main()
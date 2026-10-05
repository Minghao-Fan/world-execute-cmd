"""python -m world_execute_replica  ->  the live terminal player (same as `python -m world_execute_replica.live`)."""
import sys

from world_execute_replica.live.player import main

if __name__ == "__main__":
    sys.exit(main())

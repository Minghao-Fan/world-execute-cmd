"""Live terminal player: render the TUI PV frame by frame into a cmd/terminal window.

    python -m world_execute_replica.live [--song input/song.mp3] [--cols 160] [--rows 46]

The left pane is a text-simulated dsh chat; the right pane is the real TUI engine
letterboxed into half-block truecolor characters. The song plays through ffplay
and the picture follows the audio clock (pause / seek / resume included).
"""

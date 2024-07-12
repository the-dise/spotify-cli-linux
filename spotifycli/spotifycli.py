#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""a command line interface to Spotify on Linux"""

import argparse
import os
import sys
import datetime
from subprocess import Popen, PIPE

import dbus
import lyricwikia


def main():
    if len(sys.argv) == 1:
        start_shell()
        return 0

    global client
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in get_arguments():
        parser.add_argument(argument[0], help=argument[1], action="store_true")
    parser.add_argument("--client", action="store", dest="client", help="sets client's dbus name", default="spotify")
    args = parser.parse_args()
    client = args.client

    output = []

    for arg in sys.argv[1:]:
        if arg.startswith('--') and arg != '--client':
            func_name = f'show_{arg[2:]}'
            action_name = f'perform_{arg[2:]}'
            if func_name in globals():
                output.append(globals()[func_name]())
            elif action_name in globals():
                globals()[action_name]()

    print(' - '.join(filter(None, output)))


def start_shell():
    while True:
        try:
            command = input('spotify > ').strip()
        except EOFError:
            print("Have a nice day!")
            exit(0)

        pid = os.fork()

        if pid == 0:  # if executing context is child process
            os.execlp('spotifycli', 'spotifycli', '--{}'.format(command))
        elif pid > 0:
            os.waitpid(pid, 0)  # wait for child to exit
        else:
            print("Error during call to fork()")
            exit(1)


def get_arguments():
    return [
        ("--version", "shows version number"),
        ("--status", "shows song name and artist"),
        ("--statusposition", "shows song name and artist, with current playback position"),
        ("--statusshort", "shows status in a short way"),
        ("--song", "shows the song name"),
        ("--songshort", "shows the song name in a short way"),
        ("--artist", "shows artist name"),
        ("--artistshort", "shows artist name in a short way"),
        ("--album", "shows album name"),
        ("--position", "shows song position"),
        ("--arturl", "shows album image url"),
        ("--playbackstatus", "shows playback status"),
        ("--play", "plays the song"),
        ("--pause", "pauses the song"),
        ("--playpause", "plays or pauses the song (toggles a state)"),
        ("--lyrics", "shows the lyrics for the song"),
        ("--next", "plays the next song"),
        ("--prev", "plays the previous song")
    ]


def show_version():
    print("1.8.2")


def get_song():
    metadata = get_spotify_property("Metadata")
    artist = metadata['xesam:artist'][0]
    title = metadata['xesam:title']
    return (artist, title)


def show_status():
    artist, title = get_song()
    return f'{artist} - {title}'


def convert_timedelta(duration):
    days, seconds = duration.days, duration.seconds
    hours = days * 24 + seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = (seconds % 60)
    return str(hours).zfill(2), str(minutes).zfill(2), str(seconds).zfill(2)


def show_statusposition():
    metadata = get_spotify_property("Metadata")
    position_raw = get_spotify_property("Position")

    artist = metadata['xesam:artist'][0]
    title = metadata['xesam:title']

    # Both values are in microseconds
    position = datetime.timedelta(milliseconds=position_raw / 1000)
    length = datetime.timedelta(milliseconds=metadata['mpris:length'] / 1000)

    p_hours, p_minutes, p_seconds = convert_timedelta(position)
    l_hours, l_minutes, l_seconds = convert_timedelta(length)

    if l_hours != "00":
        # Only show hours if the song is more than an hour long
        return f'{artist} - {title} ({p_hours}:{p_minutes}:{p_seconds}/{l_hours}:{l_minutes}:{l_seconds})'
    else:
        return f'{artist} - {title} ({p_minutes}:{p_seconds}/{l_minutes}:{l_seconds})'


def show_statusshort():
    artist, title = get_song()
    artist = artist[:16] + (artist[16:] and '…')
    title = title[:12] + (title[12:] and '…')
    return f'{artist} - {title}'


def show_song():
    _, title = get_song()
    return f'{title}'


def show_songshort():
    _, title = get_song()
    title = title[:12 + (title[12:] and '…')
    return f'{title}'


def show_lyrics():
    try:
        artist, title = get_song()
        lyrics = lyricwikia.get_all_lyrics(artist, title)
        lyrics = ''.join(lyrics[0])
        return lyrics
    except BaseException:
        return 'lyrics not found'


def show_artist():
    artist, _ = get_song()
    return f'{artist}'


def show_artistshort():
    artist, _ = get_song()
    artist = artist[:15] + (artist[15:] and '…')
    return f'{artist}'


def show_playbackstatus():
    playback_status = get_spotify_property("PlaybackStatus")
    return {"Playing": '󰐊',
            "Paused": '󰏤',
            "Stopped": '󰓛'
            }[playback_status]


def show_album():
    metadata = get_spotify_property("Metadata")
    album = metadata['xesam:album']
    return f'{album}'


def show_arturl():
    metadata = get_spotify_property("Metadata")
    return "%s" % metadata['mpris:artUrl']


def get_spotify_property(spotify_property):
    try:
        session_bus = dbus.SessionBus()
        names = dbus.Interface(
            session_bus.get_object(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus"),
            "org.freedesktop.DBus").ListNames()
        mpris_name = None

        for name in names:
            if name.startswith("org.mpris.MediaPlayer2.%s" % client):
                mpris_name = name

        if mpris_name is None:
            sys.stderr.write("No mpris clients found for client %s\n" % client)
            sys.exit(1)

        spotify_bus = session_bus.get_object(
            mpris_name,
            "/org/mpris/MediaPlayer2")
        spotify_properties = dbus.Interface(
            spotify_bus,
            "org.freedesktop.DBus.Properties")
        return spotify_properties.Get(
            "org.mpris.MediaPlayer2.Player",
            spotify_property)
    except BaseException:
        sys.stderr.write("Spotify is off\n")
        sys.exit(1)


def perform_play():
    perform_spotify_action("Play")


def perform_pause():
    perform_spotify_action("Pause")


def perform_playpause():
    perform_spotify_action("PlayPause")


def perform_next():
    perform_spotify_action("Next")


def perform_prev():
    perform_spotify_action("Previous")


def perform_spotify_action(spotify_command):
    Popen('dbus-send --print-reply --dest=org.mpris.MediaPlayer2."%s" ' %
          client +
          '/org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player."%s"' %
          spotify_command, shell=True, stdout=PIPE)

def show_position():
    metadata = get_spotify_property("Metadata")
    position_raw = get_spotify_property("Position")
    # Both values are in microseconds
    position = datetime.timedelta(milliseconds=position_raw / 1000)
    length = datetime.timedelta(milliseconds=metadata['mpris:length'] / 1000)

    p_hours, p_minutes, p_seconds = convert_timedelta(position)
    l_hours, l_minutes, l_seconds = convert_timedelta(length)

    if l_hours != "00":
        # Only show hours if the song is more than an hour long
        return f'({p_hours}:{p_minutes}:{p_seconds}/{l_hours}:{l_minutes}:{l_seconds})'
    else:
        return f'({p_minutes}:{p_seconds}/{l_minutes}:{l_seconds})'


if __name__ == "__main__":
    main()

#!/usr/bin/env python

import os
import shutil
import subprocess
import argparse
import re
from collections import defaultdict

import eyed3

parser = argparse.ArgumentParser(description='Copy audio library to USB')
parser.add_argument('-s', '--source', help='Path to audio lib', required=False, default='.')
parser.add_argument('-d', '--dest', help='USB mount point', required=False, default='/Volumes/MUSIC')
parser.add_argument('-t', '--tempdir', help='Temp directory', required=False, default='temp')
parser.add_argument('-a', '--album_chars', help='Number of characters in album name to display',
                    required=False, default=None)
args = parser.parse_args()

assert os.path.exists(args.source), 'Library not found!'
assert os.path.exists(args.dest), 'USB drive not found!'

if os.path.exists(args.tempdir):
    if raw_input('temp directory exists - okay to delete? [y/N]: ').lower() != 'y':
        quit()
    shutil.rmtree(os.path.realpath(args.tempdir))

# aggregate track paths by artist, album, and track no
srcfiles = [os.path.realpath(os.path.join(dirpath, f))
            for dirpath, dirnames, files in os.walk(args.source)
            for f in files if f.endswith(('.mp3', '.aac'))]


def meta_to_artist_title_album_track(m):
    def strip(s):
        return s.replace('/', '-').replace('"', '').encode('ascii', 'ignore')

    artist = m.tag.album_artist if m.tag.album_artist else m.tag.artist
    artist = strip(re.sub('^[tT]he ', '', artist))
    title = strip(m.tag.title)
    album = strip(m.tag.album)

    order = m.tag.track_num[0]

    # strip disc num out of album name, and add a big number to the track num
    # for multi-disc albums.  The  number isn't important since we'll re-sort
    # everything below when making symlinks - we just want to keep the tracks
    # in order across albums
    disc_num_matches = re.findall(' .?[Dd]is[ck] [0-9]+.?', album)
    if len(disc_num_matches) > 0:
        disc_str = disc_num_matches[0]
        album = album.replace(disc_str, '')
        disc_num = int(re.findall('[0-9]+', disc_str)[0])
        order += disc_num * 1000
    elif m.tag.disc_num[0]:
        order += m.tag.disc_num[0] * 1000

    return artist, album, title, order

artist_album_to_tracks = defaultdict(list)
for f in srcfiles:
    try:
        artist, album, track, order = meta_to_artist_title_album_track(eyed3.load(f))
        print 'processing', artist, album, track
        artist_album_to_tracks[(artist, album)].append((order, track, f))
    except Exception as e:
        print e

# create a temp directory with symlinks to the tracks organized the way we want
# it on the USB stick - that will allow us to use rsync to to copy/update
os.mkdir(args.tempdir)
for artist, album in artist_album_to_tracks:
    for i, (track, name, path) in enumerate(sorted(artist_album_to_tracks[(artist, album)])):
        # one folder per artist, with first N chars of album name prepended
        # to each song, followed by sort order and track name.  This
        # will allow us to sort by album, and still see a bit of the track name
        fn = '{album}-{track:02d}-{name}.{ext}'.format(album=album[:args.album_chars],
                                                       track=i + 1,
                                                       name=name,
                                                       ext=path.split('.')[-1])
        dst = os.path.join(args.tempdir, artist, fn)
        if not os.path.exists(os.path.dirname(dst)):
            os.mkdir(os.path.dirname(dst))
        os.system('ln -s "{src}" "{dst}"'.format(src=path, dst=dst))

os.system('cd "{temp}"; rsync -arLv . "{dst}" --delete'.format(temp=args.tempdir,
                                                               dst=os.path.realpath(args.dest)))

# here's the gross part - we have to sort the files in the FAT32 filesystem
# to make sure they are displayed properly.  The fatsort utility will do this,
# but requires sudo
print 'Please enter your password to sort files on the USB stick'
cmd = 'diskutil unmount {dest}'.format(dest=os.path.realpath(args.dest))
stdout, _ = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()
device = re.match('Volume.* on ([a-zA-Z0-9]+) unmounted', stdout).groups()[0]
os.system('sudo fatsort /dev/{device}'.format(device=stdout))

# clean up and go home
shutil.rmtree(os.path.realpath(args.tempdir))

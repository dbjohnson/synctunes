# synctunes
Utility for copying mp3 files to a FAT32 formatted USB stick organized to play nice with Honda stereos.

## Arguments
* `-c, --config`: Path to configuration file

### or
* `-s, --source`: Root directory of audio library
* `-d, --dest`: Target directory on FAT32 drive
* `-t, --tmpdir`: Temp/working directory

## Sample configuration
```json
{"source": "/Volumes/Archive/Archive/Music",
 "dest": "/Volumes/MUSIC",
 "tmpdir": "temp",
 "album_skip": [],
 "artist_skip": ["Kindermusik", "Bodhipaksa"],
 "genre_skip": []}
 ```

## Requirements
- http://eyed3.nicfit.net
- http://fatsort.sourceforge.net


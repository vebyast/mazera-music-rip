# Astraware Mazera Music Rip

I ripped the soundtrack from Mazera 1.02 by Astraware, obtained [via
PalmDB](https://palmdb.net/app/astraware-mazera). There were some
difficulties. This repo contains the code I used to do it and an
overview of the reverse-engineering process, in case it helps anyone
else rip the music out of their ancient Palm game with lost source
code.

The rendered files can be found [on google
drive](https://drive.google.com/drive/folders/104vJNP3I7zgo-u6dxJ4jstILRg5flWkk?usp=sharing).

## Process

PalmOS packages are shipped in [the PDB container
format](https://en.wikipedia.org/wiki/PDB_(Palm_OS)). The only
available tooling for working with this format was in perl (which I
didn't want to deal with) and it's a very simple format, so I wrote a
parser for the parts of it that I needed to work with.

This produced about 40 records. Of those, 1 was detected by
[`file`](https://en.wikipedia.org/wiki/File_(command)) as an Impulse
Tracker module sound data file (about 1kb), 3 were unknown or
obviously wrongly labeled (e.g. one record was labeled as a GPG
private key) (64kb, 64kb, and 3kb), and the remainder were Impulse
Tracker sample files (varying sizes). Opening up the module file in
Impulse Tracker failed with a ton of errors.

I looked at Impulse Tracker's interface and [the docs for its module
files](https://github.com/schismtracker/schismtracker/wiki/ITTECH.TXT)
and decided that, while modern trackers support breaking samples out
into separate files like this, the program that Astraware would have
used required everything to be in a single file. Additionally, when I
implemented a parser for the IT module file header, I found that it
was referencing pattern and sample headers that were well past the end
of the 1kb module file. Given this I proceeded on the assumption that
these records were supposed to be a single Impulse Tracker module file.

The samples were easiest to place. These days there's a standard for
standalone sample files, but Impulse Tracker itself was too early to
have used it, so I assumed that these "sample files" were not
following the common standard and were something that Astraware had
put together themselves. This turned out to be roughly the case: The
first 0x50 bytes of each file were the [header of a
sample](https://github.com/schismtracker/schismtracker/wiki/ITTECH.TXT#impulse-sample-format)
and the remaining bytes were the sample data, just pulled straight out
of where they'd be in the module file and concatenated. I put the
0x50-byte sample header where the module header said it wanted a
sample header, assuming that the first record containing a sample was
actually the first sample, the second record containing a sample was
actually the second sample, etc. I then put the rest of the bytes
where the sample header's sample pointer field indicated the sample
data should be.

The patterns weren't as easy. Unlike the samples, which can be
identified by looking for the constant `IMPS` bytes, patterns are
simply a pair of lengths and then a bunch of data. The lack of
structure (and the total count, approximately 140 different patterns)
would have pushed Astraware's programmers to treat them as a big
single blob rather than individual records. The sizes - 64kb, 64kb,
3kb - suggested that they'd attempted this, but run into some
file-size limit. Without any structure they'd just hard-split the blob
at the size limit and called it a day. I therefore just concatenated
those three records and slapped them in assuming their first byte
should go where the module file header said the first pattern was.

This produced a complete, working, and internally consistent Impulse
Tracker module file. Gratifyingly, every block of data that I'd copied
started exactly where another ended and I didn't have to mangle any
addresses, strongly suggesting that I'd successfully reassembled the
original file and that it'd been broken out just by taking an existing
module file and copying chunks of it out to separate files.

The final layout was like this:

| Object                 | Start position | Size (bytes) | Origin                                             |
|------------------------|----------------|--------------|----------------------------------------------------|
| IT module file header  | 0x00000000     | 0x00000420   | PDB record 0                                       |
| IT module file message | 0x00000420     | 0x0000002e   | Not present and not reconstructed, left zeroed out |
| Sample headers         | 0x00000450     | 0x00000af0   | First 0x50 bytes of PDB records 4 to 38            |
| Patterns               | 0x00000f40     | 0x0001e689   | PDB records 1, 2, 3 concatenated                   |
| Sample PCM data blobs  | 0x0001f5c9     | 0x00046531   | All but first 0x50 bytes of PDB records 4 to 38    |

The next problem was figuring out how the game got a bunch of
different tracks - one per level at least - out of this single module
file. Inspecting the module in [OpenMPT](https://openmpt.org/)
revealed that the module file was (ab)using [`Bxx` Effect
Commands](https://wiki.openmpt.org/Manual:_Effect_Reference#Effect_Column_4)
to implement multiple loops. For example, pattern 11 ended with a
`B06` command, causing playback to jump back to position 6 to create a
loop, and pattern 32 ended with a `B0d` command to cause playback to
jump back to position 13 and create a second loop. I assumed that each
such loop was a separate music track. This turned out to be pretty
much correct and I was able to render each track to a `flac` with only
a little bit of poking at OpenMPT.

## Level names

Provided by [SuperKimVT](https://www.twitch.tv/superkimvt).

- Level 1: Master Computer
- Level 2: Desert
- Level 3: Forest
- Level 4: Mountains
- Level 5: Worm
- Level 6: Fin
- Level 7: Mazerian City

## Looping

- pattern 11 -> position 6
- pattern 32 -> position 13
- pattern 53 -> position 39
- pattern 76 -> position 70
- pattern 91 -> position 96
- pattern 109 -> position 117
- pattern 118 -> position 146
- pattern 138 -> position 147

| Track | Start position | (hex) | Loop origin position | Loop Pattern | Loop target position | Notes           |
|-------|----------------|-------|----------------------|--------------|----------------------|-----------------|
| Title | 0              | 0x00  | 11                   | 11           | 6                    |                 |
| 1     | 12             | 0x0c  | 36                   | 32           | 13                   |                 |
| 2     | 37             | 0x25  | 65                   | 53           | 39                   |                 |
| 3     | 66             | 0x42  | 95                   | 76           | 70                   |                 |
| 4     | 96             | 0x60  | 115                  | 91           | 96                   |                 |
| 5     | 116            | 0x74  | 135                  | 109          | 117                  |                 |
| 6     | 136            | 0x88  | 146                  | 118          | 146                  | does *not* loop |
| 7     | 147            | 0x93  | 166                  | 138          | 147                  |                 |

## Code

I use python 3 because it's simple and easy to read. I use
`dataclasses` to create structured containers for header data. I use
the `struct` module from Python's standard library to unpack `bytes`
objects into the structured `dataclass`es. I then use a `BytesIO`
object so I can easily write bytes into the appropriate places. It's
not the cleanest code and it'll only work on this game, but I kept it
as simple as I could within those constraints.

## TODO

Figure out if there are any extra tracks hiding in the introductions
to the level themes. For example, the music for level 2 ends at
position 65. The music for level 3 could start at position 66, play to
position 95, and loop back to position 76 before continuing: 66 -> 95
-> 76 -> 95 -> 76 -> …. Or, counterfactually, positions 66 through 72 could
belong to the music for a cutscene and the music for level 3 would
then go 72 -> 95 -> 76 -> 95 -> 76 -> ….

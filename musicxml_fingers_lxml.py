""" A script to pull fingerings and note names from
an uncompressed MusicXML file, to add to a PianoVision
formatted JSON generated from the corresponding MIDI.

Intial version: Andrew Hannum 10/28/2022

------------
Instructions
------------

From Musescore, export both an *uncompressed* MusicXML
copy of your score, as well as a MIDI file. Upload the
MIDI file to PianoVision using the desktop app, then
pull the result .json file off of the Quest via
SideQuest.

Point this script at the .musicxml and .json files via
the below variables, and it will output a new .json
named <old_file>_fingerings.json in the same directory.
"""

import json
from lxml import etree

xml_file = './scores/gradus_vol1.musicxml'
json_file = './scores/gradus_vol1.json'

def midinum_to_note(midinum):
    return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][midinum % 12] + str(int(midinum / 12) - 1)

def note_to_midinum(note):
    step = note.find('pitch').find('step').text
    octave = int(note.find('pitch').find('octave').text)
    alter = note.find('pitch').find('alter')
    midi = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"].index(step) + 12 * (octave + 1)
    if alter is not None:
        midi += int(alter.text)
    return midi

def note_finger(n):
    notations = n.find('notations')
    if notations is None:
        return -1
    technical = notations.find('technical')
    if technical is None:
        return -1
    fingering = technical.find('fingering')
    finger = fingering.text
    return finger

def enharmonic_name(n):
    name = n.find('pitch').find('step').text
    alter = n.find('pitch').find('alter')
    if alter is None:
        return name
    alter = int(alter.text)
    if alter < 0:
        for _ in range(alter * -1):
            name += "b"
    elif alter > 0:
        for _ in range(alter):
            name += "#"
    return name

def note_on(n):
    pitch = n.find('pitch')
    if pitch is None:
        return False
    if n.find('tie') is not None and n.find('tie').get('type') == 'stop':
        return False
    if n.get('print-object') == "no":
        return False
    return True

with open(xml_file, 'rb') as f:
    tree = etree.fromstring(f.read())

with open(json_file) as f:
    json_song = json.load(f)

#
#   Group JSON notes by time
#
json_notes_by_ticks = {}
for measure in json_song["tracksV2"]["right"]:
    for note in measure["notes"]:
        note["staff"] = 1
        # right_json_notes.append(note)
        if note["ticksStart"] in json_notes_by_ticks:
            json_notes_by_ticks[note["ticksStart"]] += [note]
        else:
            json_notes_by_ticks[note["ticksStart"]] = [note]
for measure in json_song["tracksV2"]["left"]:
    for note in measure["notes"]:
        note["staff"] = 2
        # left_json_notes.append(note)
        if note["ticksStart"] in json_notes_by_ticks:
            if note["note"] not in [n["note"] for n in json_notes_by_ticks[note["ticksStart"]]]:
                json_notes_by_ticks[note["ticksStart"]] += [note]
        else:
            json_notes_by_ticks[note["ticksStart"]] = [note]

#
#   Group XML notes by time
#
right_staff = tree.xpath('//note[staff[text()=1]]')
left_staff = tree.xpath('//note[staff[text()=2]]')
measures = tree.xpath('//measure')
xml_notes_by_offset = {}
offset = 0
for i, m in enumerate(measures):
    # print(f"measure {i}")
    for child in m:
        if child.find('duration') is None:
            continue
        duration = int(child.find('duration').text)
        if child.tag == 'note':
            if child.find('chord') is not None:
                offset -= duration
            if child.find('pitch') is not None and note_on(child):
                if offset in xml_notes_by_offset:
                    xml_notes_by_offset[offset] += [child]
                else:
                    xml_notes_by_offset[offset] = [child]
            offset += duration
        elif child.tag == 'backup':
            offset -= duration
        elif child.tag == 'forward':
            offset += duration

#
#   Sort both note sets by time then pitch
#
json_notes_sorted = []
ticks = sorted(json_notes_by_ticks.keys())
for t in ticks:
    for n in sorted(json_notes_by_ticks[t], key=lambda x: x["note"]):
        json_notes_sorted.append(n)

xml_notes_sorted = []
offsets = sorted(xml_notes_by_offset.keys())
for o in offsets:
    notes = xml_notes_by_offset[o]
    sorted_notes = sorted(notes, key=lambda n: note_to_midinum(n))
    
    # Remove duplicate XML notes
    # Prefer keeping any that have a fingering
    for i in reversed(range(1, len(sorted_notes))):
        if note_to_midinum(sorted_notes[i]) == note_to_midinum(sorted_notes[i-1]):
            if note_finger(sorted_notes[i]) == -1:
                sorted_notes.pop(i)
            else:
                sorted_notes.pop(i-1)
    
    xml_notes_sorted.extend(sorted_notes)

#
#   Make sure the lists match
#
for i, (j, x) in enumerate(zip(json_notes_sorted, xml_notes_sorted)):
    jnote = j['note']
    xnote = note_to_midinum(x)
    print(j['staff'], midinum_to_note(jnote), midinum_to_note(xnote), j['measureInd'])
    if jnote != xnote:
        print("Error!")
        exit()

#
#   Add fingerings (+ extra info) to JSON
#
for (j, x) in zip(json_notes_sorted, xml_notes_sorted):
    j['finger'] = int(note_finger(x))
    j['enharmonicName'] = enharmonic_name(x)

#
#   All done!
#
with open(json_file.replace(".json", "_fingers.json"), "w") as f:
    json.dump(json_song, f)
    print(f'Success!\nOutput file: {json_file.replace(".json", "_fingers.json")}')

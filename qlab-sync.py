#!/usr/bin/env python3

from oscclient import OSCClient
import subprocess
import csv
import tkinter as tk
from tkinter import filedialog
import sys
from time import time


client = OSCClient()
client.connect("127.0.0.1", 53000, 53001)

def main():
  root = tk.Tk()
  # root.geometry("500x500")
  # tk.Label(root, text="Test").pack()
  root.withdraw()

  if sys.argv[1]:
    file_path = sys.argv[1]
  else:
    file_path = filedialog.askopenfilename()

  qLabs_cues_csv = extract_qlabs_csv()
  (qLabs_groups, qLabs_networks, qLabs_audios) = parse_qlab_cues(qLabs_cues_csv)
  (groups, networks) = parse_etc_cues(file_path)
  generate_missing(qLabs_groups, qLabs_networks, qLabs_audios, groups, networks)



def run_jxa(cmd):
  result = subprocess.run(['osascript', '-l', 'JavaScript', '-e', cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
  return result.stdout.decode().strip()

def extract_qlabs_csv():
  print("Getting cues from QLabs Workspace!")
  cues_csv = run_jxa("""const qlab = Application("QLab");
  const workspace = qlab.workspaces[0];
  const qLabsCues = workspace.cues();
  for (let i = 0; i < qLabsCues.length; i++) {
    const q = qLabsCues[i]
    console.log(`"${[q.uniqueid(), q.qNumber(), q.qName(), q.parent().qName(), q.qType()].join('","')}"`)
  }""")
  return cues_csv


def parse_qlab_cues(qLabs_cues_csv):
  qLabs_groups: dict[str, str] = {} # {name: id}
  qLabs_networks : dict[str, str]= {} # {number(LQ1): parent_name}
  qLabs_audios: list[str] = [] # [parent_name]
  print("Extracting QLabs cues!")
  i = 0
  try:
    for line in csv.reader(qLabs_cues_csv.splitlines()):
      (id, number, name, parent_name, type) = line
      if type.lower() == "group":
        qLabs_groups[name] = id
      elif type.lower() == "network":
        qLabs_networks[number] = parent_name
      elif type.lower() == "audio":
        qLabs_audios.append(parent_name)
    print(f"Extracted cues")
    return (qLabs_groups, qLabs_networks, qLabs_audios)
  except ValueError:
    raise Exception("Something went wrong, are you sure you have a QLabs workspace open?")
    

def parse_etc_cues(csv_file_path: str):
  print("Parsing ETC cues!")
  groups: list[str] = [] # [name]
  networks: dict[float, tuple[str, int]] = {} # {cue_number(1.5): (scene, index)}
  current_scene = ''
  is_follow = False
  with open(csv_file_path) as f:
    index = 0
    csv_lines = f.read().split("START_TARGETS")[1].split("END_TARGETS")[0].strip().splitlines()[1:]
    for cue_data in csv.reader(csv_lines):
      cue_number = cue_data[3]
      follow = cue_data[23]
      cue_scene_start = cue_data[32]
      cue_scene_end = bool(cue_data[33])

      if cue_scene_start != '':
        current_scene = cue_scene_start
        groups.append(current_scene)
        index = 0
      if current_scene != '' and not is_follow:
        networks[cue_number] = (current_scene, index)
        index += 1
      if cue_scene_end:
        current_scene = ''
      
      if follow:
        is_follow = True
      else:
        is_follow = False

  print(f"ETC Cues parsed, total of {len(networks)} cues")
  return (groups, networks)

def generate_missing(qLabs_groups: dict[str, str], qLabs_networks: dict[str, str], qLabs_audios: list[str], groups: list[str], networks: dict[float, tuple[str, int]]):
  print("Generating missing groups")
  for group in groups:
    if not group in qLabs_groups:
      qLabs_groups[group] = client.create_group_cue().set_name(group).collapse().id
    if not group in qLabs_audios:
      client.create_cue("audio").set_name(group).move_cue(1, qLabs_groups[group])
      qLabs_audios.append(group)

  print("Generating missing network cues")
  for cue in networks:
    if f"LQ{cue}" not in qLabs_networks:
      (group, index) = networks[cue]
      client.create_network_cue().set_number(f"LQ{cue}").set_patch_number(1).set_param("cueNumber", cue).move_cue(index + 1, qLabs_groups[group])

if __name__ == '__main__':
  main()
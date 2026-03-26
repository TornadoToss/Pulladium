# Pulsar Build Script, by Erythtini

import os
import sys
import subprocess
import glob
import concurrent.futures
import datetime
import shutil

### Config
# The defaults should be fine for Windows users
# COMPILER may need to be adjusted depending on your CW path (especially for non-Windows users)
# MYDIRS exists for if you have your own modifications inside a separate folder(s) from PulsarEngine
# RIIVO should point to your pack's Binaries folder; the compiled Code.pul is copied here
# You can build in debug with -d command line argument (you will need to edit DEBUG for this to work properly)

ENGINE = "./KamekInclude"
GAMESOURCE = "./GameSource"
PULSAR = "./PulsarEngine"
BUILD = "build"
MYDIRS = []

RIIVO = ""

COMPILER = "C:/Program Files (x86)/Freescale/CW for MPC55xx and MPC56xx 2.10/PowerPC_EABI_Tools/Command_Line_Tools/mwcceppc.exe"
FLAGS = (f'-I- -i "{ENGINE}" -i "{GAMESOURCE}" -i "{PULSAR}" ' +
		 '-opt all -inline auto -enum int -fp hard -sdata 0 -sdata2 0 -maxerrors 1 -func_align 4 -MD -gccdep')
LINKER = "./KamekLinker/Kamek.exe"
DEBUG = ' -debug=0x803992E0 -map="Dolphin Emulator/Maps/RMCP01.map" -readelf="C:/MinGW/bin/readelf.exe"'

def log(log: str) -> None:
	now = datetime.datetime.now().strftime("%H:%M:%S")
	print(f"{now} {log}")

def get_deps(obj_path: str) -> list[str]:
	d_path = os.path.splitext(obj_path)[0] + ".d"
	if not os.path.exists(d_path): return []
	with open(d_path, 'r') as f:
		contents = f.read().replace("\\\n", " ").split()
		return contents[2:] # 0 is .o name, 1 is .cpp name

def should_rebuild(cpp: str, modified_h: set[str]) -> bool:
	# do we have a .o file to use? rebuild if not
	obj = os.path.join(BUILD, os.path.basename(cpp).replace(".cpp", ".o"))
	if not os.path.exists(obj): return True

	# is the .cpp more recently modified than the .o? rebuild if yes
	obj_time = os.path.getmtime(obj)
	if os.path.getmtime(cpp) > obj_time: return True

	# is any dependency of the .cpp more recently modified than the .o? rebuild if yes
	deps = get_deps(obj)
	if any(d in modified_h for d in deps):
		return True
	for dep in deps:
		if (os.path.exists(dep) and os.path.getmtime(dep) > obj_time):
			modified_h.add(dep)
			return True

	# if none of the above, no need to rebuild
	return False

def compile_cpp(cpp: str):
	obj = os.path.join(BUILD, os.path.basename(cpp).replace(".cpp", ".o"))
	cmd = f'"{COMPILER}" {FLAGS} {cpp} -o {obj}'
	log(f"Compiling {cpp}...")
	subprocess.run(cmd, shell=True)

if __name__ == "__main__":
	# add debug flags if -d argument is passed
	is_debug = False
	if len(sys.argv) > 1 and sys.argv[1] == '-d':
		FLAGS += ' -g'
		is_debug = True
		log("Compiling with debug info")

	# find every cpp that may need compiled
	cpp_files = glob.glob(f"{PULSAR}/**/*.cpp", recursive=True)
	cpp_files.append(f"{ENGINE}/kamek.cpp")
	for d in MYDIRS:
		cpp_files.extend(glob.glob(f"{d}/**/*.cpp", recursive=True))

	# delete .o files that would not be compiled from current cpp_files
	cpp_basenames = [os.path.splitext(os.path.basename(f))[0] for f in cpp_files]
	for obj in glob.glob(f"{BUILD}/*.o"):
		obj_name = os.path.splitext(os.path.basename(obj))[0]
		if not (obj_name in cpp_basenames):
			log(f"Removing {obj} as corresponding .cpp will not be built")
			os.remove(obj)

	# find which files need built
	modified_h = set()
	modified_cpps = [f for f in cpp_files if should_rebuild(f, modified_h)]
	if modified_cpps == []:
		option = input("No source or header files were modified. Type L to relink, R for full rebuild, or enter to close: ")
		if option.lower() == "r":
			modified_cpps = [f for f in cpp_files]
		elif option.lower() != "l":
			quit()
			
	# build cpp files (in parallel!)
	compile_cpp(f"{ENGINE}/kamek.cpp")
	with concurrent.futures.ThreadPoolExecutor() as executor:
		executor.map(compile_cpp, modified_cpps)

	# link objects into binary
	obj_files = glob.glob(f"{BUILD}/*.o")
	obj_string = ""
	for obj in obj_files:
		obj_string += f'"{obj}" '

	log("Linking...")
	linker_cmd = f'"{LINKER}" {obj_string} -dynamic -externals="{GAMESOURCE}/symbols.txt" -versions="{GAMESOURCE}/versions.txt" -output-combined={BUILD}/Code.pul'
	if is_debug:
		linker_cmd += DEBUG
	proc = subprocess.run(linker_cmd, shell=True)
	
	# copy binary to RIIVO
	if proc.returncode == 0 and RIIVO != "":
		log("Copying binary...")
		shutil.copy(f"{BUILD}/Code.pul", f"{RIIVO}/Code.pul")
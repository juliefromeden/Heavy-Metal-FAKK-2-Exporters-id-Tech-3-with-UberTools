# Heavy Metal FAKK 2 Exporters (id Tech 3 with UberTools)

- These scripts were created to comfortable and fast export Heavy Metal FAKK 2 original files (models, textures, animations, skeletons)
- Scripts support Heavy Metal FAKK 2 and have not been tested with converting files from games such as Alice, Star Trek, Medal of Honor etc. 
- This may work either fully or partially on files from other similar game engines
- This scripts is not for modding idTech3 games, but for converting idTech3 UberTools engine files into a formats suitable for use in modern engines

### EXPORT BSP MAP: 
- Drag and drop `.bsp` file on to `export_that_fakking_bsp.py`
- Paste path to the original extracted folders from archives of the game (pak0, pak1... etc.)
- This will create mapname folder with the `.obj` map model, all `.png` map textures and `.json` with entities coorditates

### EXPORT FTX TEXTURE: 
- Drag and drop `.ftx` file(s) on to `export_that_fakking_ftx.py`
- This will convert `.ftx` to `.png`

### EXPORT TAN MODEL: 
- Drag and drop `.tan` file(s) on to `export_that_fakking_tan.py`
- This will create modelname folder with the `.obj` model

### EXPORT SKB CHARACTER AND SKA ANIMATION: 
- Open `export_that_fakking_skb_ska.txt` and copy script
- Run that script in blender (4.5)
- Open side panel FAKK2 menu, select `.skb` and `.ska` and press import
- This will import character, bones and animation into a blender scene and automatically combine them correctly without any extra manipulation
- "Single" can import single `.ska` per `.skb`
- "Batch" can import multiple `.ska` per `.skb` and automatically creating actions

### EXPORT WAV SOUND:
- **Need ffmpeg.exe in the same folder**
- Drag and drop folder containing `.wav` sounds on to `export_that_fakking_wav.py`
- This will convert `.wav` to PCM 16-bit `.wav`

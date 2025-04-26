#open an array of photos

import os
from PIL import Image

numImages = 6

count = 0

#Get names of all files in the directory
files = os.listdir('Couch_images')

# for file in files:
#     image = Image.open('Couch_images/' + file)
#     width, height = image.size
#     for i in range(numImages):
#     #for i in range(1):
#         #Crop into 6 images, splitting horizontally
#         image.crop((i * width / numImages, 0, (i + 1) * width / numImages, height)).save('Couch_images_cropped/' + file[:-4] + f'_{i}.png')
#     count += 1

# Reorder
count = 0
for j in range(6):
    k = 5 - j    
    for i in range(12):
        i += 1
        image = Image.open(f'Couch_images_cropped/Couch_{i}_{k}.png')
        image.save(f'Couch_images_formatted/IMG_{count}.png')
        count += 1

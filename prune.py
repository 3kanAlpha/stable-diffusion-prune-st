# Copyright (C) 2022  Lopho <contact@lopho.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import sys, os
from argparse import ArgumentParser
from functools import partial

import pickle as python_pickle
from torch import save, load
from safetensors.torch import save_file, load_file

def prune(
    checkpoint,
    fp16 = False,
    ema = False,
    clip = True,
    vae = True,
    depth = True,
    unet = True,
):
    sd = checkpoint
    nested_sd = False
    if 'state_dict' in sd:
        sd = sd['state_dict']
        nested_sd = True
    sd_pruned = dict()
    for k in sd.keys():
        cp = unet and k.startswith('model.diffusion_model.')
        cp = cp or (depth and k.startswith('depth_model.'))
        cp = cp or (vae and k.startswith('first_stage_model.'))
        cp = cp or (clip and k.startswith('cond_stage_model.'))
        if cp:
            k_in = k
            if ema:
                k_ema = 'model_ema.' + k[6:].replace('.', '')
                if k_ema in sd:
                    k_in = k_ema
            sd_pruned[k] = sd[k_in].half() if fp16 else sd[k_in]
    if nested_sd:
        return { 'state_dict': sd_pruned }
    else:
        return sd_pruned

def main(args):
    parser = ArgumentParser(
        description = "Prune a stable diffusion checkpoint",
        epilog = "Copyright (C) 2022  Lopho <contact@lopho.org> | \
                Licensed under the AGPLv3 <https://www.gnu.org/licenses/>"
    )
    parser.add_argument(
        'input',
        type = str,
        help = "input checkpoint"
    )
    parser.add_argument(
        'output',
        type = str,
        help = "output checkpoint"
    )
    parser.add_argument(
        '-p', '--fp16',
        action = 'store_true',
        help = "convert to float16"
    )
    parser.add_argument(
        '-e', '--ema',
        action = 'store_true',
        help = "use EMA for weights"
    )
    parser.add_argument(
        '-c', '--no-clip',
        action = 'store_true',
        help = "strip CLIP weights"
    )
    parser.add_argument(
        '-a', '--no-vae',
        action = 'store_true',
        help = "strip VAE weights"
    )
    parser.add_argument(
        '-d', '--no-depth',
        action = 'store_true',
        help = "strip depth model weights"
    )
    parser.add_argument(
        '-u', '--no-unet',
        action = 'store_true',
        help = "strip UNet weights"
    )
    
    def error(self, message):
        sys.stderr.write(f"error: {message}\n")
        self.print_help()
        self.exit()
    parser.error = partial(error, parser) # type: ignore
    args = parser.parse_args(args)
    
    model_path = args.input
    basename = os.path.basename(model_path)
    root, ext = os.path.splitext(basename)
    
    class torch_pickle:
        class Unpickler(python_pickle.Unpickler):
            def find_class(self, module, name):
                try:
                    return super().find_class(module, name)
                except:
                    return None
                
    weights = dict()
    if ext.lower() == '.safetensors':
        weights = load_file(model_path)
    else:
        weights = load(model_path, pickle_module=torch_pickle) # type: ignore
    
    weights_pruned = prune(
        weights,
        fp16 = args.fp16,
        ema = args.ema,
        clip = not args.no_clip,
        vae = not args.no_vae,
        depth = not args.no_depth,
        unet = not args.no_unet
    )
    
    # check output extension
    output_path = args.output
    oext = os.path.splitext(output_path)[1].lower()
    
    if oext == '.safetensors':
        save_file(weights_pruned, output_path)
    else:
        save(weights_pruned, output_path)

if __name__ == '__main__':
    main(sys.argv[1:])


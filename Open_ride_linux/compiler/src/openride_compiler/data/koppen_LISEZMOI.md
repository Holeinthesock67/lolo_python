# Carte des climats de Köppen-Geiger embarquée (lot U24)

`koppen_1986_2010.u8.xz` : climats de Köppen-Geiger de la période 1986–2010, grille équirectangulaire
mondiale de 12 960 × 6 480 pixels de 100 secondes d'arc (environ 3 km), un octet par pixel, du nord au sud
puis d'ouest en est, compressée en xz (214 Ko, 84 Mo une fois lue). Codes 1 à 31 dans l'ordre de
`koppen.CODES` (Af, Am, As, Aw, BSh, BSk, BWh, BWk, Cfa, Cfb, Cfc, Csa, Csb, Csc, Cwa, Cwb, Cwc, Dfa, Dfb,
Dfc, Dfd, Dsa, Dsb, Dsc, Dsd, Dwa, Dwb, Dwc, Dwd, EF, ET), 32 pour la mer.

Lue par le compilateur seul (`openride_compiler.koppen`), sans accès réseau, pour la zone climatique des
biomes.

## Provenance

- Carte de F. Rubel, K. Brugger, K. Haslinger et I. Auer : « The climate of the European Alps: Shift of very
  high resolution Köppen-Geiger climate zones 1800–2100 », *Meteorologische Zeitschrift* 26 (2017),
  p. 115–125, doi:10.1127/metz/2016/0816 ; classification de F. Rubel et M. Kottek, *Meteorologische
  Zeitschrift* 19 (2010), p. 135–141, doi:10.1127/0941-2948/2010/0430. Données diffusées librement sur
  <http://koeppen-geiger.vu-wien.ac.at>, avec citation des auteurs.
- Copie prise dans le paquet Python `kgcpy` 1.1.8 (PyPI, fichier `kmz_int_reshape.png`, mêmes codes), dont
  F. Rubel est coauteur, diffusé sous licence BSD à trois clauses :

```
BSD 3-Clause License

Copyright (c) 2022, CWRU SDLE LAB
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided
that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the
   following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and
   the following disclaimer in the documentation and/or other materials provided with the distribution.
3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or
   promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED
WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
```

- Conversion : `python3 scripts/prepare_koppen.py chemin/vers/kmz_int_reshape.png` (pixels inchangés,
  seulement recompressés en xz).

## Remplacement possible

La carte de H. E. Beck et al. (*Scientific Data* 2018 et 2023, 1 km, licence CC BY 4.0) donnerait les mêmes
codes ; il suffirait de la réduire à cette grille et de garder le même fichier.

# cada ano espera o seu .tif baixar (baixa.sh) e roda as UFs em paralelo
cd ~/scrap_tmp/mapbiomas_raster
UFS=$(ls /home/polo/bragro_tmp/imovel/car | sed "s/sigla_uf=//")
for a in 2016 2017 2018 2019 2020 2021 2022 2023 2024; do
  until [ -s brazil_coverage_$a.tif.ok ]; do sleep 30; done
  echo $UFS | tr " " "\n" | xargs -P 8 -I{} venv/bin/python zonal.py $a {}
  echo "ANO $a FEITO"
done
echo FIM

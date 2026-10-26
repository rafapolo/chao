for a in 2016 2017 2018 2019 2020 2021 2022 2023 2024; do
  f=brazil_coverage_$a.tif; [ -s $f.ok ] && continue
  curl -sfL -m 3600 --retry 3 -o $f "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/collection_10/lulc/coverage/$f" && echo ok > $f.ok && echo "$f $(stat -c%s $f)"
done
echo FIM

mkdir output
docker run --volume "$(pwd):/src/" --entrypoint /bin/sh batonogov/pyinstaller-linux:main-slim-bullseye -c "apt update -y && apt-get install python3-tk -y && /entrypoint.sh"
mv dist/* output/
docker run --volume "$(pwd):/src/" batonogov/pyinstaller-windows:latest
mv dist/* output/

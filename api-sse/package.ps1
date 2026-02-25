# cd api-sse
# pip install -r requirements.txt -t package
# rm lambda_package.zip
cd package
Compress-Archive -Path * -DestinationPath ..\lambda_package.zip
cd ..
Compress-Archive -Path app.py, helpers.py -DestinationPath lambda_package.zip -Update
Compress-Archive -Path ./routes -DestinationPath lambda_package.zip -Update

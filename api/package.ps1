# cd api
# pip install -r requirements.txt -t package
cd package
Compress-Archive -Path * -DestinationPath ..\lambda_package.zip
cd ..
Compress-Archive -Path app.py, dynamodb_utils.py, helpers.py -DestinationPath lambda_package.zip -Update
Compress-Archive -Path ./routes, ./lib, ./examples -DestinationPath lambda_package.zip -Update

# cd api
# mkdir package
# pip install -r requirements.txt -t package
rm lambda_package.zip
cd package
Compress-Archive -Path * -DestinationPath ..\lambda_package.zip
cd ..
Compress-Archive -Path app.py, dynamodb_utils.py, helpers.py, helpers_v1.py -DestinationPath lambda_package.zip -Update
Compress-Archive -Path ./routes, ./lib, ./examples -DestinationPath lambda_package.zip -Update

function = index_invoices_to_elastic
region=eu-central-1
zip_code = $(function).zip
layer=$(function)-layer
zip_layer = $(layer).zip

zip:
	[ ! -e $(zip_code) ] || rm $(zip_code)
	#7z a -x'!_trash' -x'!__pycache__' -x'!data.json' $(zip_code) ./$(code_folder)/*
	zip -r9 $(zip_code) . -x "__pycache__/*" -x "*.ipynb" -x ".*" -x "_trash/*" -x "env/*" -x "*sh" -x "makefile" -x "events/*" -x "*zip"

update-code:
	make zip
	aws --profile ferryhopper --region $(region) lambda update-function-code --function-name $(function) --zip-file fileb://$(zip_code)
	rm $(zip_code)

update-layer:
	mkdir -p python
	# You need to create a minimal environment for the app to work. Then pip freeze it and
	# get requirements.txt
	# Furthermore we assume that that
	# 1. docker service is running;
	# 2. you have the appropriate requirements.txt file in current directory; use pip freeze, not pipreqs
	# 3. you don't use a directory named 'python' in the current folder  
	# Now, create package according to an aws-like docker environment:
	docker run --rm -v $(shell pwd):/foo -w /foo lambci/lambda:build-python3.8 \
		pip install -r requirements.txt --no-deps -t python
	zip -r9 $(zip_layer) python
	sudo rm -rf python # sudo because docker user modified contents 
	aws --profile ferryhopper --region $(region) lambda publish-layer-version --layer-name $(layer) --zip-file fileb://$(zip_layer) --compatible-runtimes python3.8
	rm $(zip_layer)

	# Alternatively, first store to S3 then publish; does not work when bucket and layers are in different region:
	#aws --profile ferryhopper s3 cp $(zip_layer) s3://$(bucket)/Lambda/Layers/$(zip_layer)
	#aws --profile ferryhopper lambda publish-layer-version --layer-name $(layer) --content S3Bucket=$(bucket),S3Key=Lambda/Layers/$(layer).zip --compatible-runtimes python3.8

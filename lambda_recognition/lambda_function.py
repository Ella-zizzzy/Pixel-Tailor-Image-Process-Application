#
# Python program to open and process a picture, recognizing labels from the picture.
# When users upload a picture, download the pic automatically,
# recognize tha picture by AWS Recognition. 
# Only save the first five labels of the picture, save in RDS
#
#

import json
import uuid
import base64
import pathlib
import datatier
import urllib.parse
import string

import boto3
import pymysql
import os

from configparser import ConfigParser

def lambda_handler(event, context):
  try:
    print("**STARTING**")
    print("**lambda: final_proj_recognition**")
    

    #
    # setup AWS based on config file:
    #
    config_file = 'final-project-config.ini'
    os.environ['AWS_SHARED_CREDENTIALS_FILE'] = config_file
    
    configur = ConfigParser()
    configur.read(config_file)
    print("**config read**")
    #
    # configure for S3 access:
    #
    s3_profile = 's3readwrite'
    boto3.setup_default_session(profile_name=s3_profile)
    
    bucketname = configur.get('s3', 'bucket_name')
    
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(bucketname)
    print("**s3 access**")
    #
    # configure for Rekognition access:
    #
    rekognition = boto3.client('rekognition')
    print("**rekognition access**")

    #
    # configure for RDS access
    #
    rds_endpoint = configur.get('rds', 'endpoint')
    rds_portnum = int(configur.get('rds', 'port_number'))
    rds_username = configur.get('rds', 'user_name')
    rds_pwd = configur.get('rds', 'user_pwd')
    rds_dbname = configur.get('rds', 'db_name')
    print("**RDS access**")
    #
    # this function is event-driven by a photo being
    # dropped into S3. The bucket key is sent to 
    # us and obtain as follows:
    #

    #pic_bucketname =urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['name'], encoding='utf-8')
     
    bucketkey = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    print("image bucketkey from event:", bucketkey)
    
      
    #
    # download photo from S3 to LOCAL file system:
    #
    print("**DOWNLOADING '", bucketkey, "'**")

    #
    # Download photo in the local directory where we have access.
    #
    local_filename = f'/tmp/{bucketkey.split("/")[-1]}'
    print("**filename**")
    print(local_filename)
    
    bucket.download_file(bucketkey, local_filename)#do we need to use bucketname?

    #
    # open LOCAL photo file:
    #
    print("**PROCESSING local photo**")
    
    #reader = PdfReader(local_pdf)
    #number_of_pages = len(reader.pages)

    with open(local_filename, 'rb') as image_file:
            image_bytes = image_file.read()

    
    response = rekognition.detect_labels(
      Image={'Bytes':image_bytes},
      MaxLabels = 5
    )



    #Select the last created photo id and user id
    #
    # open connection to the database:
    #
    print("**Opening DB connection**")
    #
    dbConn = datatier.get_dbConn(rds_endpoint, rds_portnum, rds_username, rds_pwd, rds_dbname)

    sql_get_photoid = """SELECT photoid, userid FROM photos ORDER BY photoid DESC LIMIT 1;"""
    result = datatier.retrieve_one_row(dbConn, sql_get_photoid)

    photoid, userid = result
    print("photoid and userid")
    print(photoid)
    print(userid)

    #
    #Store every label we recognized in to the table Labels
    #with the photo id and user id
    #

    all_labels = []

    for label in response['Labels']:
      label_name = label['Name']
      confidence = label['Confidence'] #there is confidence for every label, save or not?
      all_labels.append(label_name)

      # insert label in to Labels table
      insert_sql = """INSERT INTO labels (photoid, userid, labelname) VALUES (%s, %s, %s)"""
      
      datatier.perform_action(dbConn, insert_sql, [photoid, userid, label_name])
    
    #
    # done!
    #
    # respond in an HTTP-like way, i.e. with a status
    # code and body in JSON format:
    #
    print("**DONE, returning success**")
    
    return {
      'statusCode': 200,
      'body': json.dumps({"message": "Photo recognized successfully.", "Photo with labels": all_labels})
      
    }

    
  #
  # on an error, try to upload error message to S3:
  #
  except Exception as err:
    print("**ERROR when recognition photo**")
    print(str(err))
     
    return {
      'statusCode': 500,
      'body': json.dumps(str(err))
    }

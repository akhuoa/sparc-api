from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
from botocore.exceptions import ClientError
from app.config import Config
from scripts.email_sender import EmailSender
import json 
import requests
import logging
from flask_marshmallow import Marshmallow
# from blackfynn import Blackfynn
from app.serializer import ContactRequestSchema
# from pymongo import MongoClient
# import logging


app = Flask(__name__)
# set environment variable
app.config['ENV'] = Config.DEPLOY_ENV

cors = CORS(app, resources={r"*": {"origins": Config.SPARC_APP_HOST}})

ma = Marshmallow(app)
email_sender = EmailSender()
mongo = None
bf = None
s3 = boto3.client('s3',
                  aws_access_key_id=Config.SPARC_PORTAL_AWS_KEY,
                  aws_secret_access_key=Config.SPARC_PORTAL_AWS_SECRET,
                  region_name='us-east-1'
                  )


# @app.before_first_request
# def connect_to_blackfynn():
#     global bf
#     bf = Blackfynn(
#         api_token=Config.BLACKFYNN_API_TOKEN,
#         api_secret=Config.BLACKFYNN_API_SECRET,
#         env_override=False,
#         host=Config.BLACKFYNN_API_HOST
#     )

# @app.before_first_request
# def connect_to_mongodb():
#     global mongo
#     mongo = MongoClient(Config.MONGODB_URI)


@app.route('/health')
def health():
    return json.dumps({ "status": "healthy" })


@app.route("/contact", methods=["POST"])
def contact():
    data = json.loads(request.data)
    contact_request = ContactRequestSchema().load(data)

    name = contact_request["name"]
    email = contact_request["email"]
    message = contact_request["message"]

    email_sender.send_email(name, email, message)

    return json.dumps({"status": "sent"})

# Returns a list of embargoed (unpublished) datasets
# @api_blueprint.route('/datasets/embargo')
# def embargo():
#     collection = mongo[Config.MONGODB_NAME][Config.MONGODB_COLLECTION]
#     embargo_list = list(collection.find({}, {'_id':0}))
#     return json.dumps(embargo_list)


# Download a file from S3
@app.route('/download')
def create_presigned_url(expiration=3600):
    bucket_name = 'blackfynn-discover-use1'
    key = request.args.get('key')
    response = s3.generate_presigned_url('get_object',
                                         Params={
                                             'Bucket': bucket_name,
                                             'Key': key,
                                             'RequestPayer': 'requester'
                                         },
                                         ExpiresIn=expiration)

    return response

@app.route('/sim/dataset/<id>')
def sim_dataset(id):
    if request.method == 'GET':
        req = requests.get('{}/datasets/{}'.format(Config.DISCOVER_API_HOST, id))
        json = req.json()
        inject_markdown(json)
        inject_template_data(json)
        return jsonify(json)

def inject_markdown(resp):
    if 'readme' in resp:
        mark_req = requests.get(resp.get('readme'))
        resp['markdown'] = mark_req.text

def inject_template_data(resp):
    id = resp.get('id')
    version = resp.get('version')
    if (id is None or version is None):
        return

    try:
        response = s3.get_object(Bucket='blackfynn-discover-use1',
                                 Key='{}/{}/files/template.json'.format(id, version),
                                 RequestPayer='requester')
    except ClientError as e:
        # If the file is not under folder 'files', check under folder 'packages'
        logging.warning('Required file template.json was not found under /files folder, trying under /packages...')
        try:
            response = s3.get_object(Bucket='blackfynn-discover-use1',
                                     Key='{}/{}/packages/template.json'.format(id, version),
                                     RequestPayer='requester')
        except ClientError as e2:
            logging.error(e2)
            return

    template = response['Body'].read()

    try:
        template_json = json.loads(template)
    except ValueError as e:
        logging.error(e)
        return

    resp['study'] = {'uuid': template_json.get('uuid'),
                     'name': template_json.get('name'),
                     'description': template_json.get('description')}


@app.route("/project/<project_id>", methods=["GET"])
def datasets_by_project_id(project_id):

    #1 - call discover to get awards on all datasets (let put a very high limit to make sure we do not miss any)

    req = requests.get('{}/search/records?limit=1000&offset=0&model=summary'.format(Config.DISCOVER_API_HOST))

    json = req.json()['records']

    #2 - filter response to retain only awards with project_id
    result = filter(lambda x : x['properties']['hasAwardNumber'] == project_id, json)

    ids = map(lambda x: str(x['datasetId']), result)

    separator='&ids='

    list_ids = separator.join(ids)

    #3 - get the datasets from the list of ids from #2

    if len(list_ids) > 0:
        return requests.get('{}/datasets?ids={}'.format(Config.DISCOVER_API_HOST, list_ids))
    else:
        return




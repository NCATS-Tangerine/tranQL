"""
Provide a standard protocol for asking graph oriented questions of Translator data sources.
"""
import copy
import argparse
import json
import os
import yaml
import jsonschema
import requests
from flask import Flask, request, abort, Response, send_from_directory
from flask_restful import Api, Resource
from flasgger import Swagger
from flask_cors import CORS
from tranql.concept import ConceptModel
from tranql.lib.ndex import NDEx
from tranql.main import TranQL
import networkx as nx
from tranql.util import JSONKit
from tranql.concept import BiolinkModelWalker
import flask_monitoringdashboard as dashboard

web_app_root = "web/build"

app = Flask(__name__, static_folder=web_app_root)
dashboard.bind(app)

api = Api(app)
CORS(app)

""" https://github.com/NCATS-Gamma/NCATS-ReasonerStdAPI """
#filename = 'translator_interchange.yaml'
filename = os.path.join ("backplane", 'translator_interchange_0.9.0.yaml')
with open(filename, 'r') as file_obj:
    template = yaml.load(file_obj)
app.config['SWAGGER'] = {
    'title': 'TranQL API',
    'description': 'Translator Query Language (TranQL) API',
    'uiversion': 3
}
swagger = Swagger(app) #, template=template)

class StandardAPIResource(Resource):
    def validate (self, request):
        with open(filename, 'r') as file_obj:
            specs = yaml.load(file_obj)
        to_validate = specs["components"]["schemas"]["Message"]
        to_validate["components"] = specs["components"]
        to_validate["components"].pop("Message", None)
        try:
            jsonschema.validate(request.json, to_validate)
        except jsonschema.exceptions.ValidationError as error:
            print (f"ERROR: {str(error)}")
            abort(Response(str(error), 400))
    
class TranQLQuery(StandardAPIResource):
    """ TranQL Resource. """

    def __init__(self):
        super().__init__()
        
    def post(self):
        """
        query
        ---
        tag: validation
        description: TranQL Query
        requestBody:
            description: Input message
            required: true
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            query:
                                type: string
        responses:
            '200':
                description: Success
                content:
                    text/plain:
                        schema:
                            type: string
                            example: "Successfully validated"
            '400':
                description: Malformed message
                content:
                    text/plain:
                        schema:
                            type: string

        """
        #self.validate (request)
        tranql = TranQL ()
        print (request.json)
        query = request.json['query'] if 'query' in request.json else ''
        print (f"----------> query: {query}")
        context = tranql.execute (query) #, cache=True)
        result = context.mem.get ('result', {})
        return result

class ModelConceptsQuery(StandardAPIResource):
    """ Query model concepts. """

    def __init__(self):
        super().__init__()
        
    def post(self):
        """
        query
        ---
        tag: validation
        description: TranQL Query
        requestBody:
            description: Input message
            required: true
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            query:
                                type: string
        responses:
            '200':
                description: Success
                content:
                    text/plain:
                        schema:
                            type: string
                            example: "Successfully validated"
            '400':
                description: Malformed message
                content:
                    text/plain:
                        schema:
                            type: string

        """
        #self.validate (request)
        '''
        print (f"----> request -> {json.dumps(request.json, indent=2)}")
        print (request.json)
        query = request.json['query'] if 'query' in request.json else ''
        print (f"----------> query: {query}")
        '''
        concept_model = ConceptModel ("biolink-model")
        concepts = sorted (list(concept_model.by_name.keys ()))
        print (concepts)
        return concepts


class ModelRelationsQuery(StandardAPIResource):
    """ Query model relations. """

    def __init__(self):
        super().__init__()
        
    def post(self):
        """
        query
        ---
        tag: validation
        description: TranQL concept model relations query.
        requestBody:
            description: Input message
            required: true
            content:
                application/json:
                    schema:
                        type: object
                        properties:
                            query:
                                type: string
        responses:
            '200':
                description: Success
                content:
                    text/plain:
                        schema:
                            type: string
                            example: "Successfully validated"
            '400':
                description: Malformed message
                content:
                    text/plain:
                        schema:
                            type: string

        """
        #self.validate (request)
        '''
        print (f"----> request -> {json.dumps(request.json, indent=2)}")
        query = request.json['query'] if 'query' in request.json else ''
        print (f"----------> query: {query}")
        '''
        concept_model = ConceptModel ("biolink-model")
        relations = sorted (list(concept_model.relations_by_name.keys ()))
        print (relations)
        return relations

###############################################################################################
#
# Define routes.
#
###############################################################################################

api.add_resource(TranQLQuery, '/tranql/query')
api.add_resource(ModelConceptsQuery, '/tranql/model/concepts')
api.add_resource(ModelRelationsQuery, '/tranql/model/relations')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Short sample app')
    parser.add_argument('-port', action="store", dest="port", default=8100, type=int)
    args = parser.parse_args()
    server_host = '0.0.0.0'
    server_port = args.port
    app.run(
        host=server_host,
        port=server_port,
        debug=False,
        use_reloader=True
    )
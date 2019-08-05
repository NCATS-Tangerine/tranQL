"""
Provide a standard protocol for asking graph oriented questions of Translator data sources.
"""
import copy
import argparse
import json
import logging
import os
import traceback
import yaml
import jsonschema
import requests
from flask import Flask, request, abort, Response, send_from_directory
from flask_restful import Api, Resource
from flasgger import Swagger
from flask_cors import CORS
from tranql.concept import ConceptModel
from tranql.main import TranQL
from tranql.tranql_ast import SelectStatement
import networkx as nx
from tranql.util import JSONKit
from tranql.tranql_schema import GraphTranslator, Schema
from tranql.concept import BiolinkModelWalker
from tranql.exception import TranQLException
#import flask_monitoringdashboard as dashboard

logger = logging.getLogger (__name__)

web_app_root = os.path.join (os.path.dirname (__file__), "..", "web", "build")

app = Flask(__name__, static_folder=web_app_root)
#dashboard.bind(app)

api = Api(app)
CORS(app)

app.config['SWAGGER'] = {
    'title': 'TranQL API',
    'description': 'Translator Query Language (TranQL) API',
    'uiversion': 3,
    'swagger': '3.2.0'
}
swagger = Swagger(app)

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
            logging.error (f"ERROR: {str(error)}")
            abort(Response(str(error), 400))
    def handle_exception (self, e, warning=False):
        result = {"errors": []}
        if isinstance (e, list):
            [result["errors"].extend(self.handle_exception(exception)["errors"]) for exception in e]
        elif isinstance (e, TranQLException):
            result["errors"].append({
                "message" : str(e),
                "details" : str(e.details) if e.details else ''
            })
        elif isinstance (e, Exception):
            result["errors"].append({
                "message" : str(e),
                "details" : ''
            })
        elif isinstance (e, str):
            result["errors"].extend(self.handle_exception(Exception(e))["errors"])

        traceback.print_exc ()

        if warning:
            result["status"] = "Warning"
        else:
            result["status"] = "Error"


        return result

class WebAppRoot(Resource):
    def get(self):
        """
        webapp root
        ---
        consumes': [ 'text/plain' ]
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
        return send_from_directory(web_app_root, 'index.html')
api.add_resource(WebAppRoot, '/', endpoint='webapp_root')

class WebAppPath(Resource):
    def get(self, path):
        """
        webapp
        ---
        parameters:
            - in: path
              name: path
              type: string
              required: true
              description: Resource path.
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
        resource_path = os.path.join (os.path.dirname (__file__), os.path.sep, path)
        logger.debug (f"--path: {resource_path}")
        if path != "" and os.path.exists(web_app_root + "/" + path):
            return send_from_directory(web_app_root, path)
        else:
            abort (404)
api.add_resource(WebAppPath, '/<path:path>', endpoint='webapp_path')


class Configuration(StandardAPIResource):
    """ Configuration """
    def get(self):
        """
        configuration
        ---
        tag: validation
        description: TranQL Query
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
        return {
            "api_url" : config['API_URL'],
            "robokop_url" : config['ROBOKOP_URL']
        }
class MergeKG(StandardAPIResource):
    """ Exposes an endpoint that allows for the merging of an arbitrary number of knowledge graphs """

    def __init__(self):
        super().__init__()

    def post(self):
        """
        query
        ---
        tag: validation
        description: Merge Knowledge Graphs
        parameters:
            - in: query
              name: knowledge_graphs
              schema:
                type: array
              description: An array of KGS 0.9.0 compliant knowledge graph objects
            - in: query
              name: interpreter_options
              schema:
                type: object
              description: Any options to pass to the TranQL interpreter (such as 'name_based_merging' or 'resolve_names')
              required: false
              default: {}
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
        messages = [{'knowledge_graph' : i, 'knowledge_map' : []} for i in request.json.get('knowledge_graphs',[])]
        tranql = TranQL (options=request.json.get('interpreter_options',{}))
        return SelectStatement.merge_results(messages,tranql)
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
        parameters:
            - in: query
              name: query
              schema:
                type: string
              description: A TranQL query
            - in: query
              name: dynamicIdResolution
              schema:
                type: boolean
              required: false
              default: false
              description: Specifies if dynamic id lookup of curies will be performed
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
        result = {}

        logging.debug (request.json)
        query = request.json.get('query','')
        dynamicIdResolution = request.json.get('dynamicIdResolution',False)
        logging.debug (f"--> query: {query}")
        tranql = TranQL (options = {
        "dynamic_id_resolution" : dynamicIdResolution
        })

        try:
            context = tranql.execute (query) #, cache=True)
            result = context.mem.get ('result', {})
            logger.debug (f" -- backplane: {context.mem.get('backplane', '')}")
            if len(context.mem.get ('requestErrors', [])) > 0:
                errors = self.handle_exception(context.mem['requestErrors'], warning=True)
                result.update(errors)
        except Exception as e:
            traceback.print_exc()
            errors = [e, *tranql.context.mem.get ('requestErrors', [])]
            result = self.handle_exception (errors)
        with open ('query.out', 'w') as stream:
            json.dump (result, stream, indent=2)
        return result

class AnnotateGraph(StandardAPIResource):
    """ Request the message object to be annotated by the backplane and return the annotated message """

    def __init__(self):
        super().__init__()

    def post(self):
        """
        query
        ---
        tag: validation
        description: Graph annotator.
        parameters:
            - in: query
              name: message
              schema:
                type: object
              description: KGS 0.1.0 compliant message object
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
        tranql = TranQL ()
        messageObject = request.json['message']
        url = tranql.context.mem.get('backplane') + '/graph/gnbr/decorate'

        logger.info(url)

        resp = requests.post(
            url = url,
            json = messageObject,
            headers = {
                'accept': 'text/plain'
            }
        )

        data = resp.json()

        for result in data['results']:
            type = result['result_type']
            if type in messageObject:
                messageObject[type] = result['result_graph']

        return messageObject

class SchemaGraph(StandardAPIResource):
    """ Graph of schema to display to the client """

    def __init__(self):
        super().__init__()

    def get(self):
        """
        query
        ---
        tag: validation
        description: Get the TranQL schema
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
        tranql = TranQL ()
        schema = Schema (backplane=tranql.context.mem.get('backplane'))
        schemaGraph = GraphTranslator(schema.schema_graph)

        # logger.info(schema.schema_graph.net.nodes)
        # logger.info(schemaGraph.graph_to_message())

        # return {"nodes":[],"links":[]}
        obj = {
            "schema": schemaGraph.graph_to_message(),
        }
        if len(schema.loadErrors) > 0:
            errors = self.handle_exception(schema.loadErrors, warning=True)
            for key in errors:
                obj[key] = errors[key]
        return obj

class ModelConceptsQuery(StandardAPIResource):
    """ Query model concepts. """

    def __init__(self):
        super().__init__()

    def post(self):
        """
        query
        ---
        tag: validation
        description: Get biolink model concepts
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
        result = {}
        try:
            concept_model = ConceptModel ("biolink-model")
            result = sorted (list(concept_model.by_name.keys ()))
            logging.debug (result)
        except Exception as e:
            #traceback.print_exc (e)
            result = self.handle_exception (e)
        return result


class ModelRelationsQuery(StandardAPIResource):
    """ Query model relations. """

    def __init__(self):
        super().__init__()

    def post(self):
        """
        query
        ---
        tag: validation
        description: Get biolink model relations
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
        result = {}
        try:
            concept_model = ConceptModel ("biolink-model")
            result = sorted (list(concept_model.relations_by_name.keys ()))
            logging.debug (result)
        except Exception as e:
            #traceback.print_exc (e)
            result = self.handle_exception (e)
        return result

###############################################################################################
#
# Define routes.
#
###############################################################################################

api.add_resource(TranQLQuery, '/tranql/query')
api.add_resource(SchemaGraph, '/tranql/schema')
api.add_resource(AnnotateGraph, '/tranql/annotate')
api.add_resource(MergeKG,'/tranql/merge_knowledge_graphs')
api.add_resource(ModelConceptsQuery, '/tranql/model/concepts')
api.add_resource(ModelRelationsQuery, '/tranql/model/relations')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Short sample app')
    parser.add_argument('--host', action="store", dest="host", default='0.0.0.0')
    parser.add_argument('--port', action="store", dest="port", default=8001, type=int)
    parser.add_argument('-d', '--debug', help="Debug log level.", default=False, action='store_true')
    parser.add_argument('-r', '--reloader', help="Use reloader independent of debug.", default=False, action='store_true')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    app.run(
        host=args.host,
        port=args.port,
        debug=args.debug,
        use_reloader=args.debug or args.reloader
    )

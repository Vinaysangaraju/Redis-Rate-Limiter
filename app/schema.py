from marshmallow import Schema, fields


class TierResponseSchema(Schema):
    message = fields.String(required=True)


class RateLimitErrorSchema(Schema):
    error = fields.String(required=True)
    message = fields.String(required=True)


class ForbiddenErrorSchema(Schema):
    error = fields.String(required=True)
    message = fields.String(required=True)
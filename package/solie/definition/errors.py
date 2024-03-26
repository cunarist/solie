import json


class ApiRequestError(Exception):
    def __init__(self, info_text: str, payload: dict | None):
        error_message = info_text
        if payload:
            error_message += "\n"
            error_message += json.dumps(payload, indent=2)
        super().__init__(error_message)


class SimulationError(Exception):
    pass

class WorkflowError(Exception):
    pass


class RetryableToolError(WorkflowError):
    pass

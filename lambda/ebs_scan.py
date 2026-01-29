import boto3

def _ec2():
    # Uses your default AWS CLI credentials & region.
    return boto3.Session().client('ec2')

def get_unattached_ebs_volumes():
    """Return EBS volumes that are not attached to any instance (status=available)."""
    ec2 = _ec2()
    resp = ec2.describe_volumes(
        Filters=[{'Name': 'status', 'Values': ['available']}]
    )
    return resp.get('Volumes', [])

def get_attached_ebs_volumes():
    """
    Return EBS volumes that are attached (status=in-use), including which instance(s)
    they are attached to. (Multi-attach rare, but we handle a list)
    """
    ec2 = _ec2()
    resp = ec2.describe_volumes(
        Filters=[{'Name': 'status', 'Values': ['in-use']}]
    )
    out = []
    for v in resp.get('Volumes', []):
        instance_ids = [a.get('InstanceId') for a in v.get('Attachments', []) if a.get('InstanceId')]
        out.append({
            'VolumeId': v.get('VolumeId'),
            'Size': v.get('Size'),
            'State': v.get('State'),                 # in-use
            'VolumeType': v.get('VolumeType'),       # e.g. gp3
            'AvailabilityZone': v.get('AvailabilityZone'),
            'InstanceIds': instance_ids or []
        })
    return out

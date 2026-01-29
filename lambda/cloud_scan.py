import boto3
from botocore.exceptions import NoCredentialsError, ProfileNotFound

def get_ec2_instances():
    try:
        session = boto3.Session()  # Uses your default credentials
        ec2 = session.client('ec2')
        response = ec2.describe_instances()
        instances = []

        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instances.append(instance)
        return instances

    except ProfileNotFound:
        print("Profile not found. Check AWS CLI config.")
        return []
    except NoCredentialsError:
        print("AWS credentials not found.")
        return []
    except Exception as e:
        print(f"Error: {e}")
        return []

if __name__ == "__main__":
    ec2_instances = get_ec2_instances()
    if ec2_instances:
        print(f"{len(ec2_instances)} EC2 instances found.")
    else:
        print("No EC2 instances found.")

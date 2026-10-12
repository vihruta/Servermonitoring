import logging
import subprocess
import json
from pydantic import ValidationError

from models import SmartMetrics


logger = logging.getLogger(__name__)


def get_nvme_smartlog(smartlog_timeout: float) -> dict[str, SmartMetrics | None] | None:

    disks = get_disk_list(smartlog_timeout=smartlog_timeout)
    smart_disk_dict : dict[str, SmartMetrics | None] =  {}
    if disks is None:
        return None
    
    for disk in disks:
        smart_data = get_disk_smart(
            disk=disk,
            smartlog_timeout=smartlog_timeout
        )
        smart_disk_dict[disk] = smart_data

    return smart_disk_dict


def get_disk_list(smartlog_timeout: float) -> list[str] | None :
    try:
        result = subprocess.run(
            ['sudo', '-n', 'nvme', 'list', '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=smartlog_timeout
        )

        result.check_returncode()

        disks_data = json.loads(result.stdout)

        disks = [disk['DevicePath'] for disk in disks_data['Devices']]

        return disks
    
    except subprocess.TimeoutExpired as exception:
        logger.exception('Timeout while nvme get disk list| %s %s',
                         exception,
                         exception.stderr
                         )
        return None
    
    except subprocess.CalledProcessError as exception:
        logger.exception('Nvme error %s, %s',
                         exception,
                         exception.stderr)
        return None
    
    except json.JSONDecodeError as exception:
        logger.exception('Error while deconding SMART JSON | %s ',
                         exception)
        return None
    
    except FileNotFoundError:
        logger.exception('No command in system')
        return None

    except Exception as exception:
        logger.exception('Error while get nvme disks list | %s',
                         exception)
        return None


def get_disk_smart(
        disk: str,
        smartlog_timeout: float) -> SmartMetrics | None:
    try:
        result = subprocess.run(
            ['sudo','-n', 'nvme', 'smart-log', disk, '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=smartlog_timeout
        )

        result.check_returncode()

        smart_json = json.loads(result.stdout)

        return SmartMetrics(
            critical_warning=smart_json['critical_warning'],
            available_spare=smart_json['available_spare'],
            percent_used=smart_json['percent_used'],
            media_errors=smart_json['media_errors'],
            num_err_log_entries=smart_json['num_err_log_entries']
        )
    
    except json.JSONDecodeError as exception:
        logger.exception('Error while deconding SMART JSON. Disk %s | %s',
                         disk,
                         exception)
        return None
    
    except subprocess.TimeoutExpired as exception:
        logger.exception('Timeout while nvme get smart. Disk: %s | %s %s',
                         disk,
                         exception,
                         exception.stderr
                         )
        return None
    
    except subprocess.CalledProcessError as exception:
        logger.exception('Nvme error with disk: %s | %s, %s',
                         disk,
                         exception,
                         exception.stderr)
        return None
    
    except (KeyError, TypeError, ValidationError):
        logger.exception('Invalid SMART data. Disk: %s', disk)
        return None
    
    except FileNotFoundError:
        logger.exception('No command in system')
        return None

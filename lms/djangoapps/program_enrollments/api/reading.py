"""
Python API functions related to reading program enrollments.

Outside of this subpackage, import these functions
from `lms.djangoapps.program_enrollments.api`.
"""


from organizations.models import Organization
from social_django.models import UserSocialAuth

from openedx.core.djangoapps.catalog.utils import get_programs
from third_party_auth.models import SAMLProviderConfig

from ..exceptions import (
    BadOrganizationShortNameException,
    ProgramDoesNotExistException,
    ProgramHasNoAuthoringOrganizationException,
    ProviderConfigurationException,
    ProviderDoesNotExistException
)
from ..models import ProgramCourseEnrollment, ProgramEnrollment

_STUDENT_ARG_ERROR_MESSAGE = (
    "user and external_user_key are both None; at least one must be provided."
)
_REALIZED_FILTER_ERROR_TEMPLATE = (
    "{} and {} are mutually exclusive; at most one of them may be passed in as True."
)
_STUDENT_LIST_ARG_ERROR_MESSAGE = (
    'user list and external_user_key_list are both empty or None;'
    ' At least one of the lists must be provided.'
)


def get_program_enrollment(
        program_uuid,
        user=None,
        external_user_key=None,
        curriculum_uuid=None,
):
    """
    Get a single program enrollment.

    Required arguments:
        * program_uuid (UUID|str)
        * At least one of:
            * user (User)
            * external_user_key (str)

    Optional arguments:
        * curriculum_uuid (UUID|str) [optional]

    Returns: ProgramEnrollment

    Raises: ProgramEnrollment.DoesNotExist, ProgramEnrollment.MultipleObjectsReturned
    """
    if not (user or external_user_key):
        raise ValueError(_STUDENT_ARG_ERROR_MESSAGE)
    filters = {
        "user": user,
        "external_user_key": external_user_key,
        "curriculum_uuid": curriculum_uuid,
    }
    return ProgramEnrollment.objects.get(
        program_uuid=program_uuid, **_remove_none_values(filters)
    )


def get_program_course_enrollment(
        program_uuid,
        course_key,
        user=None,
        external_user_key=None,
        curriculum_uuid=None,
):
    """
    Get a single program-course enrollment.

    Required arguments:
        * program_uuid (UUID|str)
        * course_key (CourseKey|str)
        * At least one of:
            * user (User)
            * external_user_key (str)

    Optional arguments:
        * curriculum_uuid (UUID|str) [optional]

    Returns: ProgramCourseEnrollment

    Raises:
        * ProgramCourseEnrollment.DoesNotExist
        * ProgramCourseEnrollment.MultipleObjectsReturned
    """
    if not (user or external_user_key):
        raise ValueError(_STUDENT_ARG_ERROR_MESSAGE)
    filters = {
        "program_enrollment__user": user,
        "program_enrollment__external_user_key": external_user_key,
        "program_enrollment__curriculum_uuid": curriculum_uuid,
    }
    return ProgramCourseEnrollment.objects.get(
        program_enrollment__program_uuid=program_uuid,
        course_key=course_key,
        **_remove_none_values(filters)
    )


def fetch_program_enrollments(
        program_uuid,
        curriculum_uuids=None,
        users=None,
        external_user_keys=None,
        program_enrollment_statuses=None,
        realized_only=False,
        waiting_only=False,
):
    """
    Fetch program enrollments for a specific program.

    Required argument:
        * program_uuid (UUID|str)

    Optional arguments:
        * curriculum_uuids (iterable[UUID|str])
        * users (iterable[User])
        * external_user_keys (iterable[str])
        * program_enrollment_statuses (iterable[str])
        * realized_only (bool)
        * waiting_only (bool)

    Optional arguments are used as filtersets if they are not None.
    At most one of (realized_only, waiting_only) may be provided.

    Returns: queryset[ProgramEnrollment]
    """
    if realized_only and waiting_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("realized_only", "waiting_only")
        )
    filters = {
        "curriculum_uuid__in": curriculum_uuids,
        "user__in": users,
        "external_user_key__in": external_user_keys,
        "status__in": program_enrollment_statuses,
    }
    if realized_only:
        filters["user__isnull"] = False
    if waiting_only:
        filters["user__isnull"] = True
    return ProgramEnrollment.objects.filter(
        program_uuid=program_uuid, **_remove_none_values(filters)
    )


def fetch_program_course_enrollments(
        program_uuid,
        course_key,
        curriculum_uuids=None,
        users=None,
        external_user_keys=None,
        program_enrollment_statuses=None,
        program_enrollments=None,
        active_only=False,
        inactive_only=False,
        realized_only=False,
        waiting_only=False,
):
    """
    Fetch program-course enrollments for a specific program and course run.

    Required argument:
        * program_uuid (UUID|str)
        * course_key (CourseKey|str)

    Optional arguments:
        * curriculum_uuids (iterable[UUID|str])
        * users (iterable[User])
        * external_user_keys (iterable[str])
        * program_enrollment_statuses (iterable[str])
        * program_enrollments (iterable[ProgramEnrollment])
        * active_only (bool)
        * inactive_only (bool)
        * realized_only (bool)
        * waiting_only (bool)

    Optional arguments are used as filtersets if they are not None.
    At most one of (realized_only, waiting_only) may be provided.
    At most one of (active_only, inactive_only) may be provided.

    Returns: queryset[ProgramCourseEnrollment]
    """
    if active_only and inactive_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("active_only", "inactive_only")
        )
    if realized_only and waiting_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("realized_only", "waiting_only")
        )
    filters = {
        "program_enrollment__curriculum_uuid__in": curriculum_uuids,
        "program_enrollment__user__in": users,
        "program_enrollment__external_user_key__in": external_user_keys,
        "program_enrollment__status__in": program_enrollment_statuses,
        "program_enrollment__in": program_enrollments,
    }
    if active_only:
        filters["status"] = "active"
    if inactive_only:
        filters["status"] = "inactive"
    if realized_only:
        filters["program_enrollment__user__isnull"] = False
    if waiting_only:
        filters["program_enrollment__user__isnull"] = True
    return ProgramCourseEnrollment.objects.filter(
        program_enrollment__program_uuid=program_uuid,
        course_key=course_key,
        **_remove_none_values(filters)
    )


def fetch_program_enrollments_by_student(
        user=None,
        external_user_key=None,
        program_uuids=None,
        curriculum_uuids=None,
        program_enrollment_statuses=None,
        realized_only=False,
        waiting_only=False,
):
    """
    Fetch program enrollments for a specific student.

    Required arguments (at least one must be provided):
        * user (User)
        * external_user_key (str)

    Optional arguments:
        * provided_uuids (iterable[UUID|str])
        * curriculum_uuids (iterable[UUID|str])
        * program_enrollment_statuses (iterable[str])
        * realized_only (bool)
        * waiting_only (bool)

    Optional arguments are used as filtersets if they are not None.
    At most one of (realized_only, waiting_only) may be provided.

    Returns: queryset[ProgramEnrollment]
    """
    if not (user or external_user_key):
        raise ValueError(_STUDENT_ARG_ERROR_MESSAGE)
    if realized_only and waiting_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("realized_only", "waiting_only")
        )
    filters = {
        "user": user,
        "external_user_key": external_user_key,
        "program_uuid__in": program_uuids,
        "curriculum_uuid__in": curriculum_uuids,
        "status__in": program_enrollment_statuses,
    }
    if realized_only:
        filters["user__isnull"] = False
    if waiting_only:
        filters["user__isnull"] = True
    return ProgramEnrollment.objects.filter(**_remove_none_values(filters))


def fetch_program_course_enrollments_by_students(
        users=None,
        external_user_keys=None,
        program_uuids=None,
        curriculum_uuids=None,
        course_keys=None,
        program_enrollment_statuses=None,
        active_only=False,
        inactive_only=False,
        realized_only=False,
        waiting_only=False,
):
    """
    Fetch program-course enrollments for a specific list of students.

    Required arguments (at least one must be provided):
        * users (iterable[User])
        * external_user_keys (iterable[str])

    Optional arguments:
        * provided_uuids (iterable[UUID|str])
        * curriculum_uuids (iterable[UUID|str])
        * course_keys (iterable[CourseKey|str])
        * program_enrollment_statuses (iterable[str])
        * realized_only (bool)
        * waiting_only (bool)

    Optional arguments are used as filtersets if they are not None.
    At most one of (realized_only, waiting_only) may be provided.
    At most one of (active_only, inactive_only) may be provided.

    Returns: queryset[ProgramCourseEnrollment]
    """
    if not (users or external_user_keys):
        raise ValueError(_STUDENT_LIST_ARG_ERROR_MESSAGE)

    if active_only and inactive_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("active_only", "inactive_only")
        )
    if realized_only and waiting_only:
        raise ValueError(
            _REALIZED_FILTER_ERROR_TEMPLATE.format("realized_only", "waiting_only")
        )
    filters = {
        "program_enrollment__user__in": users,
        "program_enrollment__external_user_key__in": external_user_keys,
        "program_enrollment__program_uuid__in": program_uuids,
        "program_enrollment__curriculum_uuid__in": curriculum_uuids,
        "course_key__in": course_keys,
        "program_enrollment__status__in": program_enrollment_statuses,
    }
    if active_only:
        filters["status"] = "active"
    if inactive_only:
        filters["status"] = "inactive"
    if realized_only:
        filters["program_enrollment__user__isnull"] = False
    if waiting_only:
        filters["program_enrollment__user__isnull"] = True
    return ProgramCourseEnrollment.objects.filter(**_remove_none_values(filters))


def _remove_none_values(dictionary):
    """
    Return a dictionary where key-value pairs with `None` as the value
    are removed.
    """
    return {
        key: value for key, value in dictionary.items() if value is not None
    }


def get_users_by_external_keys(program_uuid, external_user_keys):
    """
    Given a program and a set of external keys,
    return a dict from external user keys to Users.

    Args:
        program_uuid (UUID|str):
            uuid for program these users is/will be enrolled in
        external_user_keys (sequence[str]):
            external user keys used by the program creator's IdP.

    Returns: dict[str: User|None]
        A dict mapping external user keys to Users.
        If an external user key is not registered, then None is returned instead
            of a User for that key.

    Raises:
        ProgramDoesNotExistException
        ProgramHasNoAuthoringOrganizationException
        BadOrganizationShortNameException
        ProviderDoesNotExistsException
        ProviderConfigurationException
    """
    saml_provider = get_saml_provider_for_program(program_uuid)
    social_auth_uids = {
        saml_provider.get_social_auth_uid(external_user_key)
        for external_user_key in external_user_keys
    }
    social_auths = UserSocialAuth.objects.filter(uid__in=social_auth_uids)
    found_users_by_external_keys = {
        saml_provider.get_remote_id_from_social_auth(social_auth): social_auth.user
        for social_auth in social_auths
    }
    # Default all external keys to None, because external keys
    # without a User will not appear in `found_users_by_external_keys`.
    users_by_external_keys = {key: None for key in external_user_keys}
    users_by_external_keys.update(found_users_by_external_keys)
    return users_by_external_keys


def get_external_key_by_user_and_course(user, course_key):
    """
    Returns the external_user_key of the edX account/user
    enrolled into the course

    Arguments:
        user (User):
            The edX account representing the user in auth_user table
        course_key (CourseKey|str):
            The course key of the course user is enrolled in

    Returns: external_user_key (str|None)
        The external user key provided by Masters degree provider
        Or None if cannot find edX user to Masters learner mapping
    """
    program_course_enrollments = ProgramCourseEnrollment.objects.filter(
        course_enrollment__user=user,
        course_key=course_key
    ).order_by('status', '-modified')

    if not program_course_enrollments:
        return None

    relevant_pce = program_course_enrollments.first()
    return relevant_pce.program_enrollment.external_user_key


def get_saml_provider_for_program(program_uuid):
    """
    Return currently configured SAML provider for the Organization
    administering the given program.

    Arguments:
        program_uuid (UUID|str)

    Returns: SAMLProvider

    Raises:
        ProgramDoesNotExistException
        ProgramHasNoAuthoringOrganizationException
        BadOrganizationShortNameException
    """
    program = get_programs(uuid=program_uuid)
    if program is None:
        raise ProgramDoesNotExistException(program_uuid)
    authoring_orgs = program.get('authoring_organizations')
    org_key = authoring_orgs[0].get('key') if authoring_orgs else None
    if not org_key:
        raise ProgramHasNoAuthoringOrganizationException(program_uuid)
    try:
        organization = Organization.objects.get(short_name=org_key)
    except Organization.DoesNotExist:
        raise BadOrganizationShortNameException(org_key)
    return get_saml_provider_for_organization(organization)


def get_saml_provider_for_organization(organization):
    """
    Return currently configured SAML provider for the given Organization.

    Arguments:
        organization: Organization

    Returns: SAMLProvider

    Raises:
        ProviderDoesNotExistsException
        ProviderConfigurationException
    """
    try:
        provider_config = organization.samlproviderconfig_set.current_set().get(enabled=True)
    except SAMLProviderConfig.DoesNotExist:
        raise ProviderDoesNotExistException(organization)
    except SAMLProviderConfig.MultipleObjectsReturned:
        raise ProviderConfigurationException(organization)
    return provider_config


def get_provider_slug(provider_config):
    """
    Returns slug identifying a SAML provider.

    Arguments:
        provider_config: SAMLProvider

    Returns: str
    """
    return provider_config.provider_id.strip('saml-')

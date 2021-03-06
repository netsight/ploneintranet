from collective.workspace.interfaces import IWorkspace
from plone import api
from Products.CMFPlacefulWorkflow.PlacefulWorkflowTool \
    import WorkflowPolicyConfig_id
from zope.globalrequest import getRequest
from ploneintranet.workspace.utils import get_storage
from ploneintranet.workspace.utils import parent_workspace
from ploneintranet.workspace.config import INTRANET_USERS_GROUP_ID
from ploneintranet.workspace import MessageFactory as _
from ploneintranet.workspace.interfaces import IGroupingStoragable
from ploneintranet.workspace.interfaces import IGroupingStorage
from OFS.interfaces import IObjectWillBeRemovedEvent
from zope.component import getAdapter
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from Acquisition import aq_base
from OFS.CopySupport import cookie_path


WORKSPACE_INTERFACE = 'collective.workspace.interfaces.IHasWorkspace'


def workspace_state_changed(ob, event):
    """
    when a workspace is made 'open', we need to
    give all intranet users the 'Guest' role

    equally, when the workspace is not open, we need
    to remove the role again
    """
    workspace = event.object
    roles = ['Guest', ]
    if event.new_state.id == 'open':
        api.group.grant_roles(
            groupname=INTRANET_USERS_GROUP_ID,
            obj=workspace,
            roles=roles,
        )
        workspace.reindexObjectSecurity()
    elif event.old_state.id == 'open':
        api.group.revoke_roles(
            groupname=INTRANET_USERS_GROUP_ID,
            obj=workspace,
            roles=roles,
        )
        workspace.reindexObjectSecurity()


def workspace_added(ob, event):
    """
    when a workspace is created, we add the creator to
    the admin group. We then setup our placeful workflow

    """
    # Whoever creates the workspace should be added as an Admin
    creator = ob.Creator()
    IWorkspace(ob).add_to_team(
        user=creator,
        groups=set(['Admins']),
    )

    # Configure our placeful workflow
    cmfpw = 'CMFPlacefulWorkflow'
    ob.manage_addProduct[cmfpw].manage_addWorkflowPolicyConfig()

    # Set the policy for the config
    pc = getattr(ob, WorkflowPolicyConfig_id)
    pc.setPolicyIn('')
    pc.setPolicyBelow('ploneintranet_policy')


def participation_policy_changed(ob, event):
    """ Move all the existing users to a new group """
    workspace = IWorkspace(ob)
    old_group_name = workspace.group_for_policy(event.old_policy)
    old_group = api.group.get(old_group_name)
    for member in old_group.getAllGroupMembers():
        groups = workspace.get(member.getId()).groups
        groups -= set([event.old_policy.title()])
        groups.add(event.new_policy.title())


def invitation_accepted(event):
    """
    When an invitation is accepted, add the user to the team
    """
    request = getRequest()
    storage = get_storage()
    if event.token_id not in storage:
        return

    ws_uid, username = storage[event.token_id]
    storage[event.token_id]
    acl_users = api.portal.get_tool('acl_users')
    acl_users.updateCredentials(
        request,
        request.response,
        username,
        None
    )
    catalog = api.portal.get_tool(name="portal_catalog")
    brain = catalog.unrestrictedSearchResults(UID=ws_uid)[0]
    with api.env.adopt_roles(["Manager"]):
        ws = IWorkspace(brain.getObject())
        for name in ws.members:
            member = api.user.get(username=name)
            if member is not None:
                if member.getUserName() == username:
                    api.portal.show_message(
                        _('Oh boy, oh boy, you are already a member'),
                        request,
                    )
                    break
        else:
            ws.add_to_team(user=username)
            api.portal.show_message(
                _('Welcome to our family, Stranger'),
                request,
            )


def user_deleted_from_site_event(event):
    """ Remove deleted user from all the workspaces where he
    is a member """
    userid = event.principal

    catalog = api.portal.get_tool('portal_catalog')
    query = {'object_provides': WORKSPACE_INTERFACE}

    query['workspace_members'] = userid
    workspaces = [
        IWorkspace(b._unrestrictedGetObject())
        for b in catalog.unrestrictedSearchResults(query)
    ]
    for workspace in workspaces:
        workspace.remove_from_team(userid)


def _update_workspace_groupings(obj, event):
    """ If the relevant object is inside a workspace, the workspace grouping
        parameters (for the sidebar) need to be updated.
    """
    parent = parent_workspace(obj)
    if parent is None or not IGroupingStoragable.providedBy(parent):
        return

    storage = getAdapter(parent, IGroupingStorage)
    if IObjectRemovedEvent.providedBy(event) or \
            IObjectWillBeRemovedEvent.providedBy(event):
        storage.remove_from_groupings(obj)
    else:
        storage.update_groupings(obj)


def content_object_added_to_workspace(obj, event):
    _update_workspace_groupings(obj, event)


def content_object_edited_in_workspace(obj, event):
    _update_workspace_groupings(obj, event)


def content_object_removed_from_workspace(obj, event):
    _update_workspace_groupings(obj, event)


def content_object_moved(obj, event):
    # ignore if oldParent or newParent is None or if obj has just
    # been created or removed
    if event.oldParent is None or event.newParent is None:
        return
    if aq_base(event.oldParent) is aq_base(event.newParent):
        return
    if IGroupingStoragable.providedBy(event.oldParent):
        old_storage = getAdapter(event.oldParent, IGroupingStorage)
        old_storage.remove_from_groupings(obj)
    if IGroupingStoragable.providedBy(event.newParent):
        new_storage = getAdapter(event.newParent, IGroupingStorage)
        new_storage.update_groupings(obj)
    # Since OFS.CopySupport.manage_pasteObjects is called without a REQUEST
    # parameter, cb_dataValid() will still be true, because __cp will not
    # be reset. We do that manually here, so that the "paste" action will
    # disappear from the action list.
    request = getattr(obj, 'REQUEST', None)
    if request:
        request['RESPONSE'].setCookie(
            '__cp', 'deleted',
            path='%s' % cookie_path(request),
            expires='Wed, 31-Dec-97 23:59:59 GMT')
        request['__cp'] = None

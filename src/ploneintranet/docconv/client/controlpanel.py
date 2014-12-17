from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.z3cform import layout
from z3c.form import form
from zope import schema
from zope.component.hooks import getSiteManager
from zope.interface import Interface

from ploneintranet.docconv.client import DocconvMessageFactory as _
from ploneintranet.docconv.client.interfaces import IDocconv


async_methods = schema.vocabulary.SimpleVocabulary.fromItems(
    [(adapter.name, adapter.name or u"(Default)")
     for adapter in getSiteManager().registeredAdapters()
     if adapter.provided == IDocconv]
)


class IDocconvSettings(Interface):

    async_method = schema.Choice(
        title=_(u"Asynchronous Processing"),
        source=async_methods,
    )


class DocconvControlPanelForm(RegistryEditForm):
    form.extends(RegistryEditForm)
    schema = IDocconvSettings

DocconvControlPanelView = layout.wrap_form(
    DocconvControlPanelForm, ControlPanelFormWrapper)
DocconvControlPanelView.label = u"Docconv Client Settings"

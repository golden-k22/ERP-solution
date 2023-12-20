from import_export import fields, resources

from sales.models import Company, Contact

class CompanyResource(resources.ModelResource):
    class Meta:
        model = Company
        fields = ('name', 'address', 'unit', 'postal_code', 'associate')
        export_order = ('name', 'address', 'unit', 'postal_code', 'associate')

class ContactResource(resources.ModelResource):
    class Meta:
        model = Contact
        fields = ('contact_person', 'tel', 'fax', 'email', 'role')
        export_order = ('contact_person', 'tel', 'fax', 'email', 'role')

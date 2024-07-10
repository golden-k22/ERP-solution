import re

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic.list import ListView

from accounts.models import Uom
from inventory.models import Material, Asset, PPE, Hardware, Stationary, CustomerHardware
from project.models import Project
from sales.decorater import ajax_login_required
from django.http import JsonResponse, HttpResponse
from django.db import IntegrityError
from dateutil import parser as date_parser
import json
from sales.models import Company
from inventory.resources import MaterialResource, AssetResource, PPEResource, HardWareResource, StationaryResource, \
    CustomerHardWareResource
import pandas as pd
import os
import pytz
import datetime


# Create your views here.
@method_decorator(login_required, name='dispatch')
class InventoryMaterialView(ListView):
    model = Material
    template_name = "inventorys/inventory-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['materials'] = Material.objects.all()
        context['products'] = Material.objects.order_by('product_desc').values('product_desc').distinct()
        context['locations'] = Material.objects.order_by('location').values('location').distinct()
        context['material_nums'] = Material.objects.order_by('material_code').values('material_code').distinct()
        context['brands'] = Material.objects.order_by('brand').values('brand').distinct()
        context['suppliers'] = Company.objects.filter(associate="Supplier")
        context['uoms'] = Uom.objects.all()
        return context


@ajax_login_required
def materialdelete(request):
    if request.method == "POST":
        materialid = request.POST.get('materialid')
        material = Material.objects.get(id=materialid)
        material.delete()

        return JsonResponse({'status': 'ok'})


def ajax_export_materials(request):
    resource = MaterialResource()
    dataset = resource.export()
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="materials.csv"'
    return response


def ajax_import_materials(request):
    if request.method == 'POST':
        org_column_names = ["material_code", "product_desc", "supplier_name", "part_number", "color", "brand",
                            "location", "remark", "uom", "replenish_qty", "restock_qty", "stock_qty"]

        csv_file = request.FILES['file']
        contents = csv_file.read().decode('UTF-8')
        path = "temp.csv"
        f = open(path, 'w')
        f.write(contents)
        f.close()

        df = pd.read_csv(path)
        df.fillna("", inplace=True)
        column_names = list(df)

        if len(column_names) == 1:
            df = pd.read_csv(path, delimiter=';', decimal=',', encoding='utf-8')
            df.fillna("", inplace=True)
            column_names = list(df)

        dif_len = len(list(set(org_column_names) - set(column_names)))

        if dif_len == 0:
            record_count = len(df.index)
            success_record = 0
            failed_record = 0
            exist_record = 0
            for index, row in df.iterrows():
                exist_count = Material.objects.filter(material_code=row["material_code"]).count()
                if len(replenish_qty) == 0:
                    replenish_qty = 0
                else:
                    replenish_qty = int(row["replenish_qty"])
                if exist_count == 0:
                    try:
                        material = Material(
                            material_code=row["material_code"],
                            product_desc=row["product_desc"],
                            supplier_name=row["supplier_name"],
                            remark=str(row["remark"]),
                            part_number=str(row["part_number"]),
                            color=str(row["color"]),
                            brand=str(row["brand"]),
                            location=str(row["location"]),
                            uom=str(row["uom"]),
                            replenish_qty=replenish_qty,
                            restock_qty=row["restock_qty"],
                            stock_qty=row["stock_qty"],
                        )
                        material.save()
                        success_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
                else:
                    try:
                        material = Material.objects.filter(material_code=row["material_code"])[0]
                        material.material_code = row["material_code"]
                        material.product_desc = row["product_desc"]
                        material.supplier_name = str(row["supplier_name"])
                        material.remark = str(row["remark"])
                        material.part_number = str(row["part_number"])
                        material.color = str(row["color"])
                        material.brand = str(row["brand"])
                        material.location = str(row["location"])
                        material.uom = str(row["uom"])
                        material.replenish_qty = row["replenish_qty"]
                        material.restock_qty = replenish_qty
                        material.stock_qty = row["stock_qty"]
                        material.save()
                        exist_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
            os.remove(path)
            return JsonResponse({'status': 'true', 'error_code': '0', 'total': record_count, 'success': success_record,
                                 'failed': failed_record, 'exist': exist_record})
        else:
            os.remove(path)
            # column count is not equals
            return JsonResponse({'status': 'false', 'error_code': '1'})
    return HttpResponse("Ok")


def ajax_import_assets(request):
    if request.method == 'POST':
        org_column_names = ["asset_code", "supplier_name", "asset_desc", "category", "part_number", "brand", "status",
                            "type", "remark"]

        csv_file = request.FILES['file']
        contents = csv_file.read().decode('UTF-8')
        path = "temp.csv"
        f = open(path, 'w')
        f.write(contents)
        f.close()

        df = pd.read_csv(path)
        df.fillna("", inplace=True)
        column_names = list(df)

        if len(column_names) == 1:
            df = pd.read_csv(path, delimiter=';', decimal=',', encoding='utf-8')
            df.fillna("", inplace=True)
            column_names = list(df)

        dif_len = len(list(set(org_column_names) - set(column_names)))
        if dif_len == 0:
            record_count = len(df.index)
            success_record = 0
            failed_record = 0
            exist_record = 0
            for index, row in df.iterrows():
                exist_count = Asset.objects.filter(asset_code=row["asset_code"]).count()
                if exist_count == 0:
                    try:
                        asset = Asset(
                            asset_code=row["asset_code"],
                            asset_desc=row["asset_desc"],
                            supplier_name=row["supplier_name"],
                            category=str(row["category"]),
                            part_number=str(row["part_number"]),
                            type=str(row["type"]),
                            brand=str(row["brand"]),
                            status=str(row["status"]),
                            remark=str(row["remark"]),
                        )
                        asset.save()
                        success_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
                else:
                    try:
                        asset = Asset.objects.filter(asset_code=row["asset_code"])[0]
                        asset.asset_code = row["asset_code"]
                        asset.asset_desc = row["asset_desc"]
                        asset.supplier_name = str(row["supplier_name"])
                        asset.category = str(row["category"])
                        asset.part_number = str(row["part_number"])
                        asset.type = str(row["type"])
                        asset.brand = str(row["brand"])
                        asset.status = str(row["status"])
                        asset.remark = str(row["remark"])
                        asset.save()
                        exist_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
            os.remove(path)
            return JsonResponse({'status': 'true', 'error_code': '0', 'total': record_count, 'success': success_record,
                                 'failed': failed_record, 'exist': exist_record})
        else:
            os.remove(path)
            # column count is not equals
            return JsonResponse({'status': 'false', 'error_code': '1'})
    return HttpResponse("Ok")


def ajax_export_hardwares(request):
    resource = HardWareResource()
    dataset = resource.export()
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="hardwares.csv"'
    return response


def ajax_export_ppes(request):
    resource = PPEResource()
    dataset = resource.export()
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="PPE.csv"'
    return response


def ajax_export_stationary(request):
    resource = StationaryResource()
    dataset = resource.export()
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="stationarys.csv"'
    return response


def ajax_export_assets(request):
    resource = AssetResource()
    dataset = resource.export()
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="assets.csv"'
    return response


@ajax_login_required
def materialinventoryadd(request):
    if request.method == "POST":
        material_code = request.POST.get('material_code')
        product_desc = request.POST.get('product_desc')
        part_number = request.POST.get('part_number')
        color = request.POST.get('color')
        uom_id = request.POST.get('uom')
        replenish_qty = request.POST.get('replenish_qty')
        restock_qty = request.POST.get('restock_qty')
        stock_qty = request.POST.get('stock_qty')
        brand = request.POST.get('brand')
        location = request.POST.get('location')
        remark = request.POST.get('remark')
        supplier = request.POST.get('supplier')
        materialid = request.POST.get('materialid')
        if materialid == "-1":
            try:
                obj = Material(
                    material_code=material_code,
                    product_desc=product_desc,
                    part_number=part_number,
                    color=color,
                    uom=Uom.objects.get(id=int(uom_id)),
                    location=location,
                    remark=remark,
                    replenish_qty=replenish_qty,
                    restock_qty=restock_qty,
                    stock_qty=stock_qty,
                    brand=brand,
                    supplier_name=supplier,
                    photo=request.FILES.get('picture')
                )
                obj.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Material Inventory information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                materialinventory = Material.objects.get(id=materialid)
                materialinventory.material_code = material_code
                materialinventory.product_desc = product_desc
                materialinventory.part_number = part_number
                materialinventory.color = color
                materialinventory.uom = Uom.objects.get(id=uom_id)
                materialinventory.remark = remark
                materialinventory.location = location
                materialinventory.supplier_name = supplier
                materialinventory.replenish_qty = replenish_qty
                materialinventory.restock_qty = restock_qty
                materialinventory.stock_qty = stock_qty
                materialinventory.brand = brand
                if request.FILES.get('picture') is not None:
                    materialinventory.photo = request.FILES.get('picture')
                else:
                    print("Didn't update picture.")
                materialinventory.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Material Inventory information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getMaterial(request):
    if request.method == "POST":
        materialid = request.POST.get('materialid')
        material = Material.objects.get(id=materialid)
        if material.photo:
            data = {
                'material_code': material.material_code,
                'part_number': material.part_number,
                'product_desc': material.product_desc,
                'stock_qty': material.stock_qty,
                'replenish_qty': material.replenish_qty,
                'restock_qty': material.restock_qty,
                'uom': material.uom.id,
                'location': material.location,
                'remark': material.remark,
                'color': material.color,
                'brand': material.brand,
                'photo': material.photo.url,
                'supplier': material.supplier_name

            }
        else:
            data = {
                'material_code': material.material_code,
                'part_number': material.part_number,
                'product_desc': material.product_desc,
                'stock_qty': material.stock_qty,
                'replenish_qty': material.replenish_qty,
                'restock_qty': material.restock_qty,
                'uom': material.uom.id,
                'location': material.location,
                'remark': material.remark,
                'color': material.color,
                'brand': material.brand,
                'supplier': material.supplier_name,
                'photo': ''

            }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def ajax_inventory(request):
    if request.method == "POST":
        materials = Material.objects.all()

        return render(request, 'inventorys/ajax-inventory.html', {'materials': materials})


@ajax_login_required
def check_material_code(request):
    if request.method == "POST":
        if Material.objects.all().exists():
            material = Material.objects.all().order_by('-material_code')[0]
            data = {
                "status": "exist",
                "material": material.material_code
            }

            return JsonResponse(data)
        else:
            data = {
                "status": "no exist"
            }

            return JsonResponse(data)


@ajax_login_required
def ajax_filter_inventory(request):
    if request.method == "POST":
        search_location = request.POST.get('search_location')
        search_num = request.POST.get('search_num')
        search_brand = request.POST.get('search_brand')
        if search_location != "" and search_num == "" and search_brand == "":
            materials = Material.objects.filter(location__iexact=search_location)

        elif search_location != "" and search_num != "" and search_brand == "":
            materials = Material.objects.filter(location__iexact=search_location, material_code__iexact=search_num)

        elif search_location != "" and search_num != "" and search_brand != "":
            materials = Material.objects.filter(location__iexact=search_location, material_code__iexact=search_num,
                                                brand__iexact=search_brand)

        elif search_location == "" and search_num != "" and search_brand == "":
            materials = Material.objects.filter(material_code__iexact=search_num)

        elif search_location == "" and search_num != "" and search_brand != "":
            materials = Material.objects.filter(material_code__iexact=search_num, brand__iexact=search_brand)

        elif search_location == "" and search_num == "" and search_brand != "":
            materials = Material.objects.filter(brand__iexact=search_brand)

        elif search_location != "" and search_num == "" and search_brand != "":
            materials = Material.objects.filter(location__iexact=search_location, brand__iexact=search_brand)

        return render(request, 'inventorys/ajax-inventory.html', {'materials': materials})


@method_decorator(login_required, name='dispatch')
class InventoryAssetView(ListView):
    model = Asset
    template_name = "inventorys/inventory-asset-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['assets'] = Asset.objects.all()
        context['products'] = Asset.objects.order_by('asset_desc').values('asset_desc').distinct()
        context['asset_codes'] = Asset.objects.order_by('asset_code').values('asset_code').distinct()
        context['types'] = Asset.objects.order_by('type').values('type').distinct()
        context['brands'] = Asset.objects.order_by('brand').values('brand').distinct()
        context['suppliers'] = Company.objects.filter(associate="Supplier")
        return context


@ajax_login_required
def assetdelete(request):
    if request.method == "POST":
        assetid = request.POST.get('assetid')
        material = Asset.objects.get(id=assetid)
        material.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def assetinventoryadd(request):
    if request.method == "POST":
        asset_code = request.POST.get('asset_code')
        asset_desc = request.POST.get('asset_desc')
        part_number = request.POST.get('part_number')
        type = request.POST.get('type')
        remark = request.POST.get('remark')
        brand = request.POST.get('brand')
        supplier = request.POST.get('supplier')
        assetid = request.POST.get('assetid')
        warranty_expiry_date = request.POST.get('warranty_expiry_date')
        if warranty_expiry_date == "":
            warranty_expiry_date = None
        if assetid == "-1":
            try:
                obj = Asset(
                    asset_code=asset_code,
                    asset_desc=asset_desc,
                    part_number=part_number,
                    type=type,
                    warranty_expiry_date=warranty_expiry_date,
                    remark=remark,
                    brand=brand,
                    supplier_name=supplier,
                    photo=request.FILES.get('picture')
                )
                obj.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Asset Inventory information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                assetinventory = Asset.objects.get(id=assetid)
                assetinventory.asset_code = asset_code
                assetinventory.asset_desc = asset_desc
                assetinventory.part_number = part_number
                assetinventory.warranty_expiry_date = warranty_expiry_date
                assetinventory.remark = remark
                assetinventory.type = type
                assetinventory.supplier_name = supplier
                assetinventory.brand = brand
                if request.FILES.get('picture') is not None:
                    assetinventory.photo = request.FILES.get('picture')
                else:
                    print("Didn't update the picture.")
                assetinventory.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Asset Inventory information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getAsset(request):
    if request.method == "POST":
        assetid = request.POST.get('assetid')
        asset = Asset.objects.get(id=assetid)
        if asset.warranty_expiry_date is None:
            warranty_date = ""
        else:
            warranty_date = asset.warranty_expiry_date.strftime('%d %b, %Y')

        if asset.photo:
            data = {
                'asset_code': asset.asset_code,
                'part_number': asset.part_number,
                'asset_desc': asset.asset_desc,
                'brand': asset.brand,
                'type': asset.type,
                'photo': asset.photo.url,
                'supplier': asset.supplier_name,
                'warranty_expiry_date': warranty_date,
                'remark': asset.remark,

            }
        else:
            data = {
                'asset_code': asset.asset_code,
                'part_number': asset.part_number,
                'asset_desc': asset.asset_desc,
                'brand': asset.brand,
                'type': asset.type,
                'supplier': asset.supplier_name,
                'photo': '',
                'warranty_expiry_date': warranty_date,
                'remark': asset.remark,

            }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def ajax_asset(request):
    if request.method == "POST":
        assets = Asset.objects.all()

        return render(request, 'inventorys/ajax-asset.html', {'assets': assets})


@ajax_login_required
def ajax_filter_asset(request):
    if request.method == "POST":
        search_type = request.POST.get('search_type')
        search_no = request.POST.get('search_no')
        search_brand = request.POST.get('search_brand')
        if search_type != "" and search_no == "" and search_brand == "":
            assets = Asset.objects.filter(type__iexact=search_type)

        elif search_type != "" and search_no != "" and search_brand == "":
            assets = Asset.objects.filter(type__iexact=search_type, asset_code__iexact=search_no)

        elif search_type != "" and search_no != "" and search_brand != "":
            assets = Asset.objects.filter(type__iexact=search_type, asset_code__iexact=search_no,
                                          brand__iexact=search_brand)

        elif search_type == "" and search_no != "" and search_brand == "":
            assets = Asset.objects.filter(asset_code__iexact=search_no)

        elif search_type == "" and search_no != "" and search_brand != "":
            assets = Asset.objects.filter(asset_code__iexact=search_no, brand__iexact=search_brand)

        elif search_type == "" and search_no == "" and search_brand != "":
            assets = Asset.objects.filter(brand__iexact=search_brand)

        elif search_type != "" and search_no == "" and search_brand != "":
            assets = Asset.objects.filter(type__iexact=search_type, brand__iexact=search_brand)

        return render(request, 'inventorys/ajax-asset.html', {'assets': assets})


# PPE part
@method_decorator(login_required, name='dispatch')
class InventoryPPEView(ListView):
    model = PPE
    template_name = "inventorys/ppe-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ppes'] = PPE.objects.all()
        context['ppe_descs'] = PPE.objects.order_by('ppe_desc').values('ppe_desc').distinct()
        context['variants'] = PPE.objects.order_by('variant').values('variant').distinct()
        context['ppe_nums'] = PPE.objects.order_by('ppe_code').values('ppe_code').distinct()
        context['brands'] = PPE.objects.order_by('brand').values('brand').distinct()
        context['suppliers'] = Company.objects.filter(associate="Supplier")
        context['uoms'] = Uom.objects.all()
        return context


@ajax_login_required
def ppedelete(request):
    if request.method == "POST":
        ppeid = request.POST.get('ppeid')
        ppe = PPE.objects.get(id=ppeid)
        ppe.delete()

        return JsonResponse({'status': 'ok'})


def ajax_import_ppe(request):
    if request.method == 'POST':
        org_column_names = ["ppe_code", "ppe_desc", "supplier_name", "part_number", "variant", "brand", "status", "uom",
                            "replenish_qty", "restock_qty", "stock_qty"]

        csv_file = request.FILES['file']
        contents = csv_file.read().decode('UTF-8')
        path = "temp.csv"
        f = open(path, 'w')
        f.write(contents)
        f.close()

        df = pd.read_csv(path)
        df.fillna("", inplace=True)
        column_names = list(df)

        if len(column_names) == 1:
            df = pd.read_csv(path, delimiter=';', decimal=',', encoding='utf-8')
            df.fillna("", inplace=True)
            column_names = list(df)

        dif_len = len(list(set(org_column_names) - set(column_names)))

        if dif_len == 0:
            record_count = len(df.index)
            success_record = 0
            failed_record = 0
            exist_record = 0
            for index, row in df.iterrows():
                exist_count = PPE.objects.filter(ppe_code=row["ppe_code"]).count()
                if exist_count == 0:
                    try:
                        ppe = PPE(
                            ppe_code=row["ppe_code"],
                            ppe_desc=row["ppe_desc"],
                            supplier_name=row["supplier_name"],
                            variant=str(row["variant"]),
                            part_number=str(row["part_number"]),
                            status=str(row["status"]),
                            brand=str(row["brand"]),
                            uom=str(row["uom"]),
                            replenish_qty=row["replenish_qty"],
                            restock_qty=row["restock_qty"],
                            stock_qty=row["stock_qty"],
                        )
                        ppe.save()
                        success_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
                else:
                    try:
                        ppe = PPE.objects.filter(ppe_code=row["ppe_code"])[0]
                        ppe.ppe_code = row["ppe_code"]
                        ppe.ppe_desc = row["ppe_desc"]
                        ppe.supplier_name = str(row["supplier_name"])
                        ppe.status = str(row["status"])
                        ppe.part_number = str(row["part_number"])
                        ppe.variant = str(row["variant"])
                        ppe.brand = str(row["brand"])
                        ppe.uom = str(row["uom"])
                        ppe.replenish_qty = row["replenish_qty"]
                        ppe.restock_qty = row["restock_qty"]
                        ppe.stock_qty = row["stock_qty"]
                        ppe.save()
                        exist_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
            os.remove(path)
            return JsonResponse({'status': 'true', 'error_code': '0', 'total': record_count, 'success': success_record,
                                 'failed': failed_record, 'exist': exist_record})
        else:
            os.remove(path)
            # column count is not equals
            return JsonResponse({'status': 'false', 'error_code': '1'})
    return HttpResponse("Ok")


@ajax_login_required
def ppeinventoryadd(request):
    if request.method == "POST":
        ppe_code = request.POST.get('ppe_code')
        ppe_desc = request.POST.get('ppe_desc')
        part_number = request.POST.get('part_number')
        variant = request.POST.get('variant')
        uom_id = request.POST.get('uom')
        replenish_qty = request.POST.get('replenish_qty')
        restock_qty = request.POST.get('restock_qty')
        stock_qty = request.POST.get('stock_qty')
        brand = request.POST.get('brand')
        supplier = request.POST.get('supplier')
        ppeid = request.POST.get('ppeid')
        if ppeid == "-1":
            try:
                obj = PPE(
                    ppe_code=ppe_code,
                    ppe_desc=ppe_desc,
                    part_number=part_number,
                    variant=variant,
                    uom=Uom.objects.get(id=uom_id),
                    replenish_qty=replenish_qty,
                    restock_qty=restock_qty,
                    stock_qty=stock_qty,
                    brand=brand,
                    supplier_name=supplier,
                    photo=request.FILES.get('picture')
                )
                obj.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "PPE Inventory information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                ppeinventory = PPE.objects.get(id=ppeid)
                ppeinventory.ppe_code = ppe_code
                ppeinventory.ppe_desc = ppe_desc
                ppeinventory.part_number = part_number
                ppeinventory.variant = variant
                ppeinventory.uom = Uom.objects.get(id=uom_id)
                ppeinventory.supplier_name = supplier
                ppeinventory.replenish_qty = replenish_qty
                ppeinventory.restock_qty = restock_qty
                ppeinventory.stock_qty = stock_qty
                ppeinventory.brand = brand
                if request.FILES.get('picture') is not None:
                    ppeinventory.photo = request.FILES.get('picture')
                else:
                    ppeinventory.photo = ""
                ppeinventory.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "PPE Inventory information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getPPE(request):
    if request.method == "POST":
        ppeid = request.POST.get('ppeid')
        ppe = PPE.objects.get(id=ppeid)
        if ppe.photo:
            data = {
                'ppe_code': ppe.ppe_code,
                'part_number': ppe.part_number,
                'ppe_desc': ppe.ppe_desc,
                'stock_qty': ppe.stock_qty,
                'replenish_qty': ppe.replenish_qty,
                'restock_qty': ppe.restock_qty,
                'uom': ppe.uom.id,
                'variant': ppe.variant,
                'brand': ppe.brand,
                'photo': ppe.photo.url,
                'supplier': ppe.supplier_name

            }
        else:
            data = {
                'ppe_code': ppe.ppe_code,
                'part_number': ppe.part_number,
                'ppe_desc': ppe.ppe_desc,
                'stock_qty': ppe.stock_qty,
                'replenish_qty': ppe.replenish_qty,
                'restock_qty': ppe.restock_qty,
                'uom': ppe.uom.id,
                'variant': ppe.variant,
                'brand': ppe.brand,
                'supplier': ppe.supplier_name,
                'photo': ''

            }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def ajax_ppe(request):
    if request.method == "POST":
        ppes = PPE.objects.all()

        return render(request, 'inventorys/ajax-ppe.html', {'ppes': ppes})


@ajax_login_required
def ajax_filter_ppe(request):
    if request.method == "POST":
        search_variant = request.POST.get('search_variant')
        search_num = request.POST.get('search_num')
        search_brand = request.POST.get('search_brand')
        if search_variant != "" and search_num == "" and search_brand == "":
            ppes = PPE.objects.filter(variant__iexact=search_variant)

        elif search_variant != "" and search_num != "" and search_brand == "":
            ppes = PPE.objects.filter(variant__iexact=search_variant, ppe_code__iexact=search_num)

        elif search_variant != "" and search_num != "" and search_brand != "":
            ppes = PPE.objects.filter(variant__iexact=search_variant, ppe_code__iexact=search_num,
                                      brand__iexact=search_brand)

        elif search_variant == "" and search_num != "" and search_brand == "":
            ppes = PPE.objects.filter(ppe_code__iexact=search_num)

        elif search_variant == "" and search_num != "" and search_brand != "":
            ppes = PPE.objects.filter(ppe_code__iexact=search_num, brand__iexact=search_brand)

        elif search_variant == "" and search_num == "" and search_brand != "":
            ppes = PPE.objects.filter(brand__iexact=search_brand)

        elif search_variant != "" and search_num == "" and search_brand != "":
            ppes = PPE.objects.filter(variant__iexact=search_variant, brand__iexact=search_brand)

        return render(request, 'inventorys/ajax-ppe.html', {'ppes': ppes})


# Stationary part
@method_decorator(login_required, name='dispatch')
class InventoryStationaryView(ListView):
    model = Stationary
    template_name = "inventorys/stationary-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stationaries'] = Stationary.objects.all()
        context['stationary_descs'] = Stationary.objects.order_by('stationary_desc').values(
            'stationary_desc').distinct()
        context['colors'] = Stationary.objects.order_by('color').values('color').distinct()
        context['stationary_nums'] = Stationary.objects.order_by('stationary_code').values('stationary_code').distinct()
        context['brands'] = Stationary.objects.order_by('brand').values('brand').distinct()
        context['suppliers'] = Company.objects.filter(associate="Supplier")
        context['uoms'] = Uom.objects.all()
        return context


@ajax_login_required
def stationarydelete(request):
    if request.method == "POST":
        stationaryid = request.POST.get('stationaryid')
        stationary = Stationary.objects.get(id=stationaryid)
        stationary.delete()

        return JsonResponse({'status': 'ok'})


def ajax_import_stationary(request):
    if request.method == 'POST':
        org_column_names = ["stationary_code", "stationary_desc", "supplier_name", "part_number", "variant", "brand",
                            "status", "uom", "replenish_qty", "restock_qty", "stock_qty"]

        csv_file = request.FILES['file']
        contents = csv_file.read().decode('UTF-8')
        path = "temp.csv"
        f = open(path, 'w')
        f.write(contents)
        f.close()

        df = pd.read_csv(path)
        df.fillna("", inplace=True)
        column_names = list(df)

        if len(column_names) == 1:
            df = pd.read_csv(path, delimiter=';', decimal=',', encoding='utf-8')
            df.fillna("", inplace=True)
            column_names = list(df)

        dif_len = len(list(set(org_column_names) - set(column_names)))

        if dif_len == 0:
            record_count = len(df.index)
            success_record = 0
            failed_record = 0
            exist_record = 0
            for index, row in df.iterrows():
                exist_count = Stationary.objects.filter(stationary_code=row["stationary_code"]).count()
                if exist_count == 0:
                    try:
                        stationary = Stationary(
                            stationary_code=row["stationary_code"],
                            stationary_desc=row["stationary_desc"],
                            supplier_name=row["supplier_name"],
                            variant=str(row["variant"]),
                            part_number=str(row["part_number"]),
                            status=str(row["status"]),
                            brand=str(row["brand"]),
                            uom=str(row["uom"]),
                            replenish_qty=row["replenish_qty"],
                            restock_qty=row["restock_qty"],
                            stock_qty=row["stock_qty"],
                        )
                        stationary.save()
                        success_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
                else:
                    try:
                        stationary = Stationary.objects.filter(stationary_code=row["stationary_code"])[0]
                        stationary.stationary_code = row["stationary_code"]
                        stationary.stationary_desc = row["stationary_desc"]
                        stationary.supplier_name = str(row["supplier_name"])
                        stationary.status = str(row["status"])
                        stationary.part_number = str(row["part_number"])
                        stationary.variant = str(row["variant"])
                        stationary.brand = str(row["brand"])
                        stationary.uom = str(row["uom"])
                        stationary.replenish_qty = row["replenish_qty"]
                        stationary.restock_qty = row["restock_qty"]
                        stationary.stock_qty = row["stock_qty"]
                        stationary.save()
                        exist_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
            os.remove(path)
            return JsonResponse({'status': 'true', 'error_code': '0', 'total': record_count, 'success': success_record,
                                 'failed': failed_record, 'exist': exist_record})
        else:
            os.remove(path)
            # column count is not equals
            return JsonResponse({'status': 'false', 'error_code': '1'})
    return HttpResponse("Ok")


@ajax_login_required
def stationaryinventoryadd(request):
    if request.method == "POST":
        stationary_code = request.POST.get('stationary_code')
        stationary_desc = request.POST.get('stationary_desc')
        part_number = request.POST.get('part_number')
        color = request.POST.get('color')
        uom_id = request.POST.get('uom')
        replenish_qty = request.POST.get('replenish_qty')
        restock_qty = request.POST.get('restock_qty')
        stock_qty = request.POST.get('stock_qty')
        brand = request.POST.get('brand')
        supplier = request.POST.get('supplier')
        stationaryid = request.POST.get('stationaryid')
        if stationaryid == "-1":
            try:
                obj = Stationary(
                    stationary_code=stationary_code,
                    stationary_desc=stationary_desc,
                    part_number=part_number,
                    color=color,
                    uom=Uom.objects.get(id=uom_id),
                    replenish_qty=replenish_qty,
                    restock_qty=restock_qty,
                    stock_qty=stock_qty,
                    brand=brand,
                    supplier_name=supplier,
                    photo=request.FILES.get('picture')
                )
                obj.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "Stationary Inventory information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                stationaryinventory = Stationary.objects.get(id=stationaryid)
                stationaryinventory.stationary_code = stationary_code
                stationaryinventory.stationary_desc = stationary_desc
                stationaryinventory.part_number = part_number
                stationaryinventory.color = color
                stationaryinventory.uom = Uom.objects.get(id=uom_id)
                stationaryinventory.supplier_name = supplier
                stationaryinventory.replenish_qty = replenish_qty
                stationaryinventory.restock_qty = restock_qty
                stationaryinventory.stock_qty = stock_qty
                stationaryinventory.brand = brand
                if request.FILES.get('picture') is not None:
                    stationaryinventory.photo = request.FILES.get('picture')
                else:
                    stationaryinventory.photo = ""
                stationaryinventory.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "Stationary Inventory information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getStationary(request):
    if request.method == "POST":
        stationaryid = request.POST.get('stationaryid')
        stationary = Stationary.objects.get(id=stationaryid)
        if stationary.photo:
            data = {
                'stationary_code': stationary.stationary_code,
                'part_number': stationary.part_number,
                'stationary_desc': stationary.stationary_desc,
                'stock_qty': stationary.stock_qty,
                'replenish_qty': stationary.replenish_qty,
                'restock_qty': stationary.restock_qty,
                'uom': stationary.uom.id,
                'color': stationary.color,
                'brand': stationary.brand,
                'photo': stationary.photo.url,
                'supplier': stationary.supplier_name

            }
        else:
            data = {
                'stationary_code': stationary.stationary_code,
                'part_number': stationary.part_number,
                'stationary_desc': stationary.stationary_desc,
                'stock_qty': stationary.stock_qty,
                'replenish_qty': stationary.replenish_qty,
                'restock_qty': stationary.restock_qty,
                'uom': stationary.uom.id,
                'color': stationary.color,
                'brand': stationary.brand,
                'supplier': stationary.supplier_name,
                'photo': ''
            }
        return JsonResponse(json.dumps(data), safe=False)


@ajax_login_required
def check_stationary_code(request):
    if request.method == "POST":
        if Stationary.objects.all().exists():
            stationary = Stationary.objects.all().order_by('-stationary_code')[0]
            data = {
                "status": "exist",
                "stationary": stationary.stationary_code
            }

            return JsonResponse(data)
        else:
            data = {
                "status": "no exist"
            }

            return JsonResponse(data)


@ajax_login_required
def ajax_stationary(request):
    if request.method == "POST":
        stationarys = Stationary.objects.all()

        return render(request, 'inventorys/ajax-stationary.html', {'stationarys': stationarys})


@ajax_login_required
def ajax_filter_stationary(request):
    if request.method == "POST":
        search_color = request.POST.get('search_color')
        search_num = request.POST.get('search_num')
        search_brand = request.POST.get('search_brand')
        if search_color != "" and search_num == "" and search_brand == "":
            stationarys = Stationary.objects.filter(color__iexact=search_color)

        elif search_color != "" and search_num != "" and search_brand == "":
            stationarys = Stationary.objects.filter(color__iexact=search_color, stationary_code__iexact=search_num)

        elif search_color != "" and search_num != "" and search_brand != "":
            stationarys = Stationary.objects.filter(color__iexact=search_color, stationary_code__iexact=search_num,
                                                    brand__iexact=search_brand)

        elif search_color == "" and search_num != "" and search_brand == "":
            stationarys = Stationary.objects.filter(stationary_code__iexact=search_num)

        elif search_color == "" and search_num != "" and search_brand != "":
            stationarys = Stationary.objects.filter(stationary_code__iexact=search_num, brand__iexact=search_brand)

        elif search_color == "" and search_num == "" and search_brand != "":
            stationarys = Stationary.objects.filter(brand__iexact=search_brand)

        elif search_color != "" and search_num == "" and search_brand != "":
            stationarys = Stationary.objects.filter(color__iexact=search_color, brand__iexact=search_brand)

        return render(request, 'inventorys/ajax-stationary.html', {'stationarys': stationarys})


# HARDWARE part
@method_decorator(login_required, name='dispatch')
class InventoryHardwareView(ListView):
    model = Hardware
    template_name = "inventorys/hardware-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hardware_descs'] = Hardware.objects.order_by('hardware_desc').values('hardware_desc').distinct()
        context['hardware_nums'] = Hardware.objects.order_by('hardware_code').values('hardware_code').distinct()
        context['brands'] = Hardware.objects.order_by('brand').values('brand').distinct()
        context['suppliers'] = Company.objects.filter(associate="Supplier")
        context['uoms'] = Uom.objects.all()
        return context


@ajax_login_required
def hardwaredelete(request):
    if request.method == "POST":
        hardwareid = request.POST.get('hardwareid')
        hardware = Hardware.objects.get(id=hardwareid)
        hardware.delete()

        return JsonResponse({'status': 'ok'})


@ajax_login_required
def hardwareinventoryadd(request):
    if request.method == "POST":
        hardware_code = request.POST.get('hardware_code')
        hardware_desc = request.POST.get('hardware_desc')
        serial_number = request.POST.get('serial_number')
        uom_id = request.POST.get('uom')
        expiry_date = request.POST.get('expiry_date')
        licensing_date = request.POST.get('licensing_date')
        remark = request.POST.get('remark')
        stock_qty = request.POST.get('stock_qty')
        brand = request.POST.get('brand')
        supplier = request.POST.get('supplier')
        hardwareid = request.POST.get('hardwareid')

        if expiry_date=="None":
            expiry_date=None
        if licensing_date=="None":
            licensing_date=None

        if hardwareid == "-1":
            try:
                obj = Hardware(
                    hardware_code=hardware_code,
                    hardware_desc=hardware_desc,
                    serial_number=serial_number,
                    uom=Uom.objects.get(id=uom_id),
                    expiry_date=expiry_date,
                    licensing_date=licensing_date,
                    remark=remark,
                    stock_qty=stock_qty,
                    brand=brand,
                    supplier_name=supplier,
                    photo=request.FILES.get('picture')
                )
                obj.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "HardWare Inventory information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                hardwareinventory = Hardware.objects.get(id=hardwareid)
                hardwareinventory.hardware_code = hardware_code
                hardwareinventory.hardware_desc = hardware_desc
                hardwareinventory.serial_number = serial_number
                hardwareinventory.uom = Uom.objects.get(id=uom_id)
                hardwareinventory.supplier_name = supplier
                hardwareinventory.expiry_date = expiry_date
                hardwareinventory.licensing_date = licensing_date
                hardwareinventory.remark = remark
                hardwareinventory.stock_qty = stock_qty
                hardwareinventory.brand = brand
                if request.FILES.get('picture') is not None:
                    hardwareinventory.photo = request.FILES.get('picture')
                else:
                    hardwareinventory.photo = ""
                hardwareinventory.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "HardWare Inventory information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })


@ajax_login_required
def getHardware(request):
    if request.method == "POST":
        hardwareid = request.POST.get('hardwareid')
        hardware = Hardware.objects.get(id=hardwareid)
        if hardware.expiry_date is None:
            expiry_date=None
        else:
            expiry_date=hardware.expiry_date.strftime('%d %b, %Y')
        if hardware.licensing_date is None:
            licensing_date=None
        else:
            licensing_date=hardware.licensing_date.strftime('%d %b, %Y')
        if hardware.photo:
            data = {
                'hardware_code': hardware.hardware_code,
                'serial_number': hardware.serial_number,
                'hardware_desc': hardware.hardware_desc,
                'stock_qty': hardware.stock_qty,
                'expiry_date': expiry_date,
                'licensing_date': licensing_date,
                'remark': hardware.remark,
                'uom': hardware.uom.id,
                'brand': hardware.brand,
                'photo': hardware.photo.url,
                'supplier': hardware.supplier_name

            }
        else:
            data = {
                'hardware_code': hardware.hardware_code,
                'serial_number': hardware.serial_number,
                'hardware_desc': hardware.hardware_desc,
                'stock_qty': hardware.stock_qty,
                'expiry_date': expiry_date,
                'licensing_date': licensing_date,
                'remark': hardware.remark,
                'uom': hardware.uom.id,
                'brand': hardware.brand,
                'supplier': hardware.supplier_name,
                'photo': ''

            }
        return JsonResponse(json.dumps(data), safe=False)

@ajax_login_required
def checkHardwareNo(request):
    if request.method == "POST":
        if Hardware.objects.all().exists():
            hardware = Hardware.objects.all().order_by('-hardware_code')[0]
            data = {
                "status": "exist",
                "hardware_code": hardware.hardware_code.replace('H', '').split()[0]
            }

            return JsonResponse(data)
        else:
            data = {
                "status": "no exist"
            }

            return JsonResponse(data)


@ajax_login_required
def ajax_hardware(request):
    if request.method == "POST":
        hardwares = Hardware.objects.all()

        return render(request, 'inventorys/ajax-hardware.html', {'hardwares': hardwares})


@ajax_login_required
def ajax_filter_hardware(request):
    if request.method == "POST":
        search_hardware = request.POST.get('search_hardware')
        search_num = request.POST.get('search_num')
        search_brand = request.POST.get('search_brand')
        if search_hardware != "" and search_num == "" and search_brand == "":
            hardwares = Hardware.objects.filter(hardware_desc__iexact=search_hardware)

        elif search_hardware != "" and search_num != "" and search_brand == "":
            hardwares = Hardware.objects.filter(hardware_desc__iexact=search_hardware, hardware_code__iexact=search_num)

        elif search_hardware != "" and search_num != "" and search_brand != "":
            hardwares = Hardware.objects.filter(hardware_desc__iexact=search_hardware, hardware_code__iexact=search_num,
                                                brand__iexact=search_brand)

        elif search_hardware == "" and search_num != "" and search_brand == "":
            hardwares = Hardware.objects.filter(hardware_code__iexact=search_num)

        elif search_hardware == "" and search_num != "" and search_brand != "":
            hardwares = Hardware.objects.filter(hardware_code__iexact=search_num, brand__iexact=search_brand)

        elif search_hardware == "" and search_num == "" and search_brand != "":
            hardwares = Hardware.objects.filter(brand__iexact=search_brand)

        elif search_hardware != "" and search_num == "" and search_brand != "":
            hardwares = Hardware.objects.filter(hardware_desc__iexact=search_hardware, brand__iexact=search_brand)

        return render(request, 'inventorys/ajax-hardware.html', {'hardwares': hardwares})


def ajax_import_hardwares(request):
    if request.method == 'POST':
        org_column_names = ["hardware_code", "hardware_desc", "supplier_name", "serial_number", "brand", "uom",
                            "expiry_date", "licensing_date", "stock_qty", "remark"]

        csv_file = request.FILES['file']
        contents = csv_file.read().decode('UTF-8')
        path = "temp.csv"
        f = open(path, 'w')
        f.write(contents)
        f.close()

        df = pd.read_csv(path)
        df.fillna("", inplace=True)
        column_names = list(df)

        if len(column_names) == 1:
            df = pd.read_csv(path, delimiter=';', decimal=',', encoding='utf-8')
            df.fillna("", inplace=True)
            column_names = list(df)

        dif_len = len(list(set(org_column_names) - set(column_names)))

        if dif_len == 0:
            record_count = len(df.index)
            success_record = 0
            failed_record = 0
            exist_record = 0
            for index, row in df.iterrows():
                exist_count = Hardware.objects.filter(hardware_code=row["hardware_code"]).count()
                if exist_count == 0:
                    try:
                        hardware = Hardware(
                            hardware_code=row["hardware_code"],
                            hardware_desc=row["hardware_desc"],
                            serial_number=row["serial_number"],
                            supplier_name=str(row["supplier_name"]),
                            brand=str(row["brand"]),
                            uom=str(row["uom"]),
                            expiry_date=datetime.datetime.strptime(row["expiry_date"], '%m/%d/%Y').replace(
                                tzinfo=pytz.utc),
                            licensing_date=datetime.datetime.strptime(row["licensing_date"], '%m/%d/%Y').replace(
                                tzinfo=pytz.utc),
                            remark=str(row["remark"]),
                            stock_qty=row["stock_qty"],
                        )
                        hardware.save()
                        success_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
                else:
                    try:
                        hardware = Hardware.objects.filter(hardware_code=row["hardware_code"])[0]
                        hardware.hardware_code = row["hardware_code"]
                        hardware.hardware_desc = row["hardware_desc"]
                        hardware.supplier_name = str(row["supplier_name"])
                        hardware.serial_number = str(row["serial_number"])
                        hardware.remark = str(row["remark"])
                        hardware.brand = str(row["brand"])
                        hardware.uom = str(row["uom"])
                        hardware.expiry_date = row["expiry_date"]
                        hardware.licensing_date = row["licensing_date"]
                        hardware.stock_qty = row["stock_qty"]
                        hardware.save()
                        exist_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
            os.remove(path)
            return JsonResponse({'status': 'true', 'error_code': '0', 'total': record_count, 'success': success_record,
                                 'failed': failed_record, 'exist': exist_record})
        else:
            os.remove(path)
            # column count is not equals
            return JsonResponse({'status': 'false', 'error_code': '1'})
    return HttpResponse("Ok")


# HARDWARE part
@method_decorator(login_required, name='dispatch')
class CustomerHardwareView(ListView):
    model = Hardware
    template_name = "inventorys/customer-hardware-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hardware_descs'] = CustomerHardware.objects.order_by('hardware_desc').values(
            'hardware_desc').distinct()
        context['brands'] = CustomerHardware.objects.order_by('brand').values('brand').distinct()
        # context['customers'] = Company.objects.filter(associate="Supplier")
        customers = CustomerHardware.objects.order_by('customer_name').values_list('customer_name', flat=True).distinct().filter(customer_name__isnull=False)
        context['customers'] = Company.objects.filter(id__in=customers)
        projects= CustomerHardware.objects.order_by('proj_name').values_list('proj_name', flat=True).distinct().filter(proj_name__isnull=False)
        context['projects'] = Project.objects.filter(id__in=projects)
        context['uoms'] = Uom.objects.all()
        return context


@ajax_login_required
def ajax_customer_hardware(request):
    if request.method == "POST":
        hardwares = CustomerHardware.objects.all()

        return render(request, 'inventorys/ajax-customer-hardware.html', {'hardwares': hardwares})


@ajax_login_required
def getCustomerHardware(request):
    if request.method == "POST":
        hardwareid = request.POST.get('hardwareid')
        hardware = CustomerHardware.objects.get(id=hardwareid)
        if hardware.expiry_date is None:
            expiry_date=None
        else:
            expiry_date=hardware.expiry_date.strftime('%d %b, %Y')
        if hardware.licensing_date is None:
            licensing_date=None
        else:
            licensing_date=hardware.licensing_date.strftime('%d %b, %Y')
        data = {
            'serial_number': hardware.serial_number,
            'hardware_desc': hardware.hardware_desc,
            'stock_qty': hardware.stock_qty,
            'expiry_date': expiry_date,
            'licensing_date': licensing_date,
            'remark': hardware.remark,
            'uom': hardware.uom.id,
            'brand': hardware.brand,
            'customer': hardware.customer_name_id,
            'project': hardware.proj_name_id,
            'status': hardware.status,
        }
        return JsonResponse(json.dumps(data), safe=False)

@ajax_login_required
def customer_hardware_add(request):
    if request.method == "POST":
        hardware_desc = request.POST.get('hardware_desc')
        serial_number = request.POST.get('serial_number')
        uom_id = request.POST.get('uom')
        expiry_date = request.POST.get('expiry_date')
        licensing_date = request.POST.get('licensing_date')
        remark = request.POST.get('remark')
        stock_qty = request.POST.get('stock_qty')
        brand = request.POST.get('brand')
        customer = request.POST.get('customer')
        project = request.POST.get('project')
        status = request.POST.get('status')
        hardwareid = request.POST.get('hardwareid')

        if expiry_date=="None":
            expiry_date=None
        if licensing_date=="None":
            licensing_date=None

        if hardwareid == "-1":
            try:
                obj = CustomerHardware(
                    hardware_desc=hardware_desc,
                    serial_number=serial_number,
                    uom=Uom.objects.get(id=uom_id),
                    expiry_date=expiry_date,
                    licensing_date=licensing_date,
                    remark=remark,
                    stock_qty=stock_qty,
                    brand=brand,
                    customer_name_id=customer,
                    proj_name_id=project,
                    status=status,
                    # photo=request.FILES.get('picture')
                )
                obj.save()
                return JsonResponse({
                    "status": "Success",
                    "messages": "HardWare Inventory information added!"
                })
            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })
        else:
            try:
                hardwareinventory = CustomerHardware.objects.get(id=hardwareid)
                hardwareinventory.hardware_desc = hardware_desc
                hardwareinventory.serial_number = serial_number
                hardwareinventory.uom = Uom.objects.get(id=uom_id)
                hardwareinventory.customer_name_id = customer
                hardwareinventory.project_name_id = project
                hardwareinventory.expiry_date = expiry_date
                hardwareinventory.licensing_date = licensing_date
                hardwareinventory.remark = remark
                hardwareinventory.stock_qty = stock_qty
                hardwareinventory.brand = brand
                hardwareinventory.status = status
                # if request.FILES.get('picture') is not None:
                #     hardwareinventory.photo = request.FILES.get('picture')
                # else:
                #     hardwareinventory.photo = ""
                hardwareinventory.save()

                return JsonResponse({
                    "status": "Success",
                    "messages": "HardWare Inventory information updated!"
                })

            except IntegrityError as e:
                return JsonResponse({
                    "status": "Error",
                    "messages": "Error is existed!"
                })

@ajax_login_required
def customer_hardware_delete(request):
    if request.method == "POST":
        hardwareid = request.POST.get('hardwareid')
        hardware = CustomerHardware.objects.get(id=hardwareid)
        hardware.delete()

        return JsonResponse({'status': 'ok'})

@ajax_login_required
def ajax_filter_customer_hardware(request):
    if request.method == "POST":
        search_customer = request.POST.get('search_customer')
        search_brand = request.POST.get('search_brand')

        hardwares = CustomerHardware.objects.all()
        if search_customer != "":
            hardwares = hardwares.filter(customer_name_id=search_customer)

        return render(request, 'inventorys/ajax-customer-hardware.html', {'hardwares': hardwares})


def ajax_export_customer_hardwares(request):
    resource = CustomerHardWareResource()
    dataset = resource.export()
    response = HttpResponse(dataset.csv, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="customer hardwares.csv"'
    return response

def ajax_import_customer_hardwares(request):
    if request.method == 'POST':
        org_column_names = ["hardware_desc", "customer_name","proj_name", "serial_number", "brand", "uom",
                            "expiry_date", "licensing_date", "stock_qty", "remark"]

        csv_file = request.FILES['file']
        contents = csv_file.read().decode('UTF-8')
        path = "temp.csv"
        f = open(path, 'w')
        f.write(contents)
        f.close()

        df = pd.read_csv(path)
        df.fillna("", inplace=True)
        column_names = list(df)

        if len(column_names) == 1:
            df = pd.read_csv(path, delimiter=';', decimal=',', encoding='utf-8')
            df.fillna("", inplace=True)
            column_names = list(df)

        dif_len = len(list(set(org_column_names) - set(column_names)))

        if dif_len == 0:
            record_count = len(df.index)
            success_record = 0
            failed_record = 0
            exist_record = 0
            for index, row in df.iterrows():
                exist_count = CustomerHardware.objects.filter(hardware_desc=row["hardware_desc"]).count()
                if exist_count == 0:
                    try:
                        hardware = CustomerHardware(
                            hardware_desc=row["hardware_desc"],
                            serial_number=row["serial_number"],
                            customer_name=str(row["customer_name"]),
                            proj_name=str(row["proj_name"]),
                            brand=str(row["brand"]),
                            uom=str(row["uom"]),
                            expiry_date=datetime.datetime.strptime(row["expiry_date"], '%m/%d/%Y').replace(
                                tzinfo=pytz.utc),
                            licensing_date=datetime.datetime.strptime(row["licensing_date"], '%m/%d/%Y').replace(
                                tzinfo=pytz.utc),
                            remark=str(row["remark"]),
                            stock_qty=row["stock_qty"],
                            status=str(row["status"]),
                        )
                        hardware.save()
                        success_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
                else:
                    try:
                        hardware = CustomerHardware.objects.filter(hardware_desc=row["hardware_desc"])[0]
                        hardware.hardware_desc = row["hardware_desc"]
                        hardware.customer_name = str(row["customer_name"])
                        hardware.proj_name = str(row["proj_name"])
                        hardware.serial_number = str(row["serial_number"])
                        hardware.remark = str(row["remark"])
                        hardware.brand = str(row["brand"])
                        hardware.uom = str(row["uom"])
                        hardware.expiry_date = row["expiry_date"]
                        hardware.licensing_date = row["licensing_date"]
                        hardware.stock_qty = row["stock_qty"]
                        hardware.status=row["status"]
                        hardware.save()
                        exist_record += 1
                    except Exception as e:
                        print(e)
                        failed_record += 1
            os.remove(path)
            return JsonResponse({'status': 'true', 'error_code': '0', 'total': record_count, 'success': success_record,
                                 'failed': failed_record, 'exist': exist_record})
        else:
            os.remove(path)
            # column count is not equals
            return JsonResponse({'status': 'false', 'error_code': '1'})
    return HttpResponse("Ok")

@ajax_login_required
def ajax_hardware_items(request):
    if request.method == "POST":
        id = request.POST.get('id')

        customers = Company.objects.all()
        projects = Project.objects.all()
        uoms = Uom.objects.all()
        return render(request, 'inventorys/ajax-chardware-item.html', {'id': id, 'customers': customers, 'projects': projects, 'uoms':uoms})


@ajax_login_required
def customer_hardware_clone(request):
    if request.method == "POST":
        hardwareid = request.POST.get('hardwareid')
        c_hardware=CustomerHardware.objects.get(id__iexact=hardwareid)
        desc_split=re.split("-",c_hardware.hardware_desc)
        if len(desc_split)==2:
            desc_num=int(desc_split[1])+1
            description=desc_split[0]+"-"+str(desc_num)
        else:
            description = desc_split[0] + "-" +"1"
        try:
            obj = CustomerHardware(
                hardware_desc=description,
                serial_number=c_hardware.serial_number,
                uom=c_hardware.uom,
                expiry_date=c_hardware.expiry_date,
                licensing_date=c_hardware.licensing_date,
                remark=c_hardware.remark,
                stock_qty=c_hardware.stock_qty,
                brand=c_hardware.brand,
                customer_name=c_hardware.customer_name,
                proj_name=c_hardware.proj_name,
                status=c_hardware.status,
                # photo=request.FILES.get('picture')
            )
            obj.save()
            return JsonResponse({
                "status": "Success",
                "messages": "HardWare Inventory information added!"
            })
        except IntegrityError as e:
            return JsonResponse({
                "status": "Error",
                "messages": "Error is existed!"
            })



from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Datos de contacto", {"fields": ("telefono", "direccion")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Datos adicionales", {"fields": ("email", "telefono", "direccion")}),
    )
    list_display = ("username", "email", "first_name", "last_name", "is_staff")

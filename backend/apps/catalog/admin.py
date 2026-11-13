from django.contrib import admin

from .models import Category, CategoryAttributeDefinition, Product, ProductImage, ProductVariant


class CategoryAttributeDefinitionInline(admin.TabularInline):
    model = CategoryAttributeDefinition
    extra = 0
    fields = ("key", "label", "type", "required", "options", "sort_order")
    ordering = ("sort_order", "key")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CategoryAttributeDefinitionInline]


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("sku", "price_cents", "options", "weight_g", "is_active")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = (
        "storage_key_thumb",
        "alt_text",
        "sort_order",
    )
    readonly_fields = ("storage_key_thumb",)
    can_delete = True


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "store",
        "type",
        "category",
        "base_price_cents",
        "currency",
        "is_active",
    )
    list_filter = ("type", "is_active", "currency")
    search_fields = ("name", "slug")
    inlines = [ProductVariantInline, ProductImageInline]

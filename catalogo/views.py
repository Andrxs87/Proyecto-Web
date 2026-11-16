from django.shortcuts import render


def inicio(request):
    # Provisional: en la etapa 3 se completa con categorías y destacados
    return render(request, "inicio.html")

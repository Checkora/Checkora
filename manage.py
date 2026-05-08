# [DevBounty AI]: File optimized for resolution.


```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import path
from . import views

# Create a view function for the stats page
@login_required
def stats(request):
    # Render the stats page
    return render(request, 'stats.html')

# Update the URL configuration to include the view function
urlpatterns = [
    path('stats/', views.stats, name='stats'),
]
# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import, division, print_function

import re
from django.utils.six.moves import urllib
from datetime import timedelta

from PIL import Image

from django import forms
from django.conf import settings
from django.contrib.sites.models import Site
from django.template.defaultfilters import filesizeformat
from django.utils.translation import ugettext as _

from .models import Task
from .settings import MIN_ICON_H, MIN_ICON_W, ICON_CUSTOM_MAX_FILESIZE, \
                      MIN_BIG_IMAGE_W, MIN_BIG_IMAGE_H, BIG_IMAGE_MAX_FILESIZE


class TaskAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(TaskAdminForm, self).__init__(*args, **kwargs)
        
        ratio = TaskAdminForm._ratio_from_wh(MIN_ICON_W, MIN_ICON_H)
        self.fields['image'].help_text += _("""
            Push icon.
            Minimum %(min_w)dx%(min_h)d px,
            %(ratio_w)d:%(ratio_h)d aspect ratio.
            Optional (default icon will be used).
            """) % {
                'min_w': MIN_ICON_W,
                'min_h': MIN_ICON_H,
                'ratio_w': ratio[0],
                'ratio_h': ratio[1]
            }
        
        ratio = TaskAdminForm._ratio_from_wh(MIN_BIG_IMAGE_W, MIN_BIG_IMAGE_H)
        self.fields['image2'].help_text += _("""
            Big image for push in Chrome.
            Minimum %(min_w)dx%(min_h)d px,
            %(ratio_w)d:%(ratio_h)d aspect ratio.
            Optional (if so, there will be no big image).
            """) % {
                'min_w': MIN_BIG_IMAGE_W,
                'min_h': MIN_BIG_IMAGE_H,
                'ratio_w': ratio[0],
                'ratio_h': ratio[1]
            }
    
    class Meta:
        model = Task
        fields = ['title', 'message', 'url', 'is_active', 'image', 'image2', 'run_at',]
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        self._check_image(
            image,
            max_size=ICON_CUSTOM_MAX_FILESIZE*1024,  # in settings we use kb
            min_w=MIN_ICON_W,
            min_h=MIN_ICON_H
        )
        return image
    
    def clean_image2(self):
        image2 = self.cleaned_data.get('image2')
        self._check_image(
            image2,
            max_size=BIG_IMAGE_MAX_FILESIZE*1024,
            min_w=MIN_BIG_IMAGE_W,
            min_h=MIN_BIG_IMAGE_H
        )
        return image2
    
    @staticmethod
    def _ratio_from_wh(w, h):
        """Calculate aspect ratio from image w h"""
        a = w
        b = h
        while a != 0 and b != 0:
            if a > b:
                a %= b
            else:
                b %= a
        gcd = a + b
        return [w/gcd, h/gcd]
    
    def _check_image(self, image, max_size=None, min_w=None, min_h=None):
        if image:
            if max_size is not None:
                if hasattr(image, '_size') and image._size > max_size:
                    raise forms.ValidationError(
                        _("File size can't exceed %(max_size)s. This image is %(img_size)s.") % {
                            'max_size': filesizeformat(max_size),
                            'img_size': filesizeformat(image._size)
                        }
                    )
            
            img_pillow = Image.open(image)
            
            m = re.search(r'.+?\.([^.]+)$', str(image))
            file_ext = m.group(1).lower() if m else None
            if file_ext is not None:
                img_format = img_pillow.format.lower()
                if (img_format in ('png', 'gif',) and file_ext != img_format) \
                or (img_format == 'jpeg' and file_ext not in ('jpg', 'jpe', 'jpeg',)):
                    raise forms.ValidationError(
                        _("Image format doesn't match file extension. Please use another image.")
                    )
            
            # check dimensions in px
            if min_w is not None or min_h is not None:
                w, h = img_pillow.size
                err_txt = ''
                
                if min_w is not None and w < min_w:
                    err_txt += _('Image width must be minimum %(min_w)d px, this is %(w)d px.') \
                                    % { 'min_w': min_w, 'w': w }
                if min_h is not None and h < min_h:
                    err_txt += _(' Image height must be minimum %(min_h)d px, this is %(h)d px.') \
                                    % { 'min_h': min_h, 'h': h }
                if min_w is not None and min_h is not None \
                and round(min_w/min_h, 2) != round(w/h, 2):
                # rounding so we can make a small mistake in a couple of pixels,
                # the browser itself will correct that
                    ratio = TaskAdminForm._ratio_from_wh(min_w, min_h)
                    err_txt += _(' Wrong aspect ratio, %(w_ratio)d:%(h_ratio)d needed.') \
                                    % { 'w_ratio': ratio[0], 'h_ratio': ratio[1] }
                
                if err_txt:
                    raise forms.ValidationError(err_txt)
    
    def clean_run_at(self):
        run_at = self.cleaned_data.get('run_at')
        
        near_qs = Task.objects.filter(
            is_active=True,
            run_at__range=(run_at-timedelta(hours=2, minutes=59, seconds=59),
                           run_at+timedelta(hours=2, minutes=59, seconds=59))
        )
        if self.instance and self.instance.pk:  # exclude self from search
            near_qs = near_qs.exclude(id=self.instance.pk)
        if near_qs.exists():
            raise forms.ValidationError(
                _("You can't send pushes more than once per 6 hours. \
                  Please select another date and time.")
            )
        
        return run_at

    def clean_url(self):
        url = self.cleaned_data.get('url')
        
        if not settings.DEBUG:
            # replacing http with httpS - pushes will open relative
            # to service-worker domain, and it works (if non-local 127.0.0.1)
            # only in a secure context, so a push link must work over SSL
            url = re.sub(r'^http\:\/\/', 'https://', url, flags=re.I)
        
        # service-worker gets relative links, relative to it's own domain
        # so check that user provided link for the domain we control
        sites = Site.objects.all()
        if sites:
            our_domain = False
            for site in sites:
                if re.match(r'https?\:\/\/'+re.escape(site.domain)+r'\/', url, flags=re.I):
                    our_domain = True
                    break
            if not our_domain:
                raise forms.ValidationError(
                    _("Link must belong to one of your domains: %(domains)s.") \
                        % { 'domains': ', '.join([ s.domain for s in sites ]) }
                )
        
        # the link we push must work ))
        try:
            response_code = int( urllib.request.urlopen(url).getcode() )
            if response_code < 200 or response_code > 399:
                raise forms.ValidationError(
                    _("Erroneous HTTP %(response_code)d response from url.") \
                        % { 'response_code': response_code }
                )
        except IOError as e:
            raise forms.ValidationError(
                _("Got error while trying to access url: %(error_txt)s.") \
                    % { 'error_txt': str(e) }
            )
        
        return url
    
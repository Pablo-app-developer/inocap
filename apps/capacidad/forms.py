from django import forms

from .models import CapacidadSala


class CapacidadSalaForm(forms.ModelForm):
    """Edición de las entradas escalares de una capacidad (dispara recálculo).

    Aplica a métodos POR_HORAS y PERSONALIZADO (usan horas ÷ tiempo estándar).
    """

    class Meta:
        model = CapacidadSala
        fields = [
            "horas_dia_lav",
            "horas_dia_sabado",
            "tiempo_estandar_horas",
            "ajuste_sobreatencion",
            "observaciones",
        ]
        widgets = {
            "horas_dia_lav": forms.NumberInput(attrs={"step": "0.25", "min": "0"}),
            "horas_dia_sabado": forms.NumberInput(attrs={"step": "0.25", "min": "0"}),
            "tiempo_estandar_horas": forms.NumberInput(attrs={"step": "0.05", "min": "0.001"}),
            "ajuste_sobreatencion": forms.NumberInput(attrs={"step": "1"}),
            "observaciones": forms.TextInput(),
        }


class CapacidadSemanalForm(forms.ModelForm):
    """Edición del método POR_DIA_SEMANA: citas por cada día de la semana."""

    DIAS = ["citas_lun", "citas_mar", "citas_mie", "citas_jue", "citas_vie", "citas_sab", "citas_dom"]

    class Meta:
        model = CapacidadSala
        fields = [
            "citas_lun", "citas_mar", "citas_mie", "citas_jue",
            "citas_vie", "citas_sab", "citas_dom",
            "ajuste_sobreatencion", "observaciones",
        ]
        _dia = forms.NumberInput(attrs={"step": "1", "min": "0", "style": "width:4.5rem"})
        widgets = {
            "citas_lun": _dia, "citas_mar": _dia, "citas_mie": _dia, "citas_jue": _dia,
            "citas_vie": _dia, "citas_sab": _dia, "citas_dom": _dia,
            "ajuste_sobreatencion": forms.NumberInput(attrs={"step": "1", "style": "width:5rem"}),
            "observaciones": forms.TextInput(),
        }
        labels = {
            "citas_lun": "Lunes", "citas_mar": "Martes", "citas_mie": "Miércoles",
            "citas_jue": "Jueves", "citas_vie": "Viernes", "citas_sab": "Sábado",
            "citas_dom": "Domingo",
        }

    def dias_fields(self):
        """Los 7 campos de día en orden, para renderizar la rejilla."""
        return [self[name] for name in self.DIAS]

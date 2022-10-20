from math import pi, ceil, floor
from scipy import stats
import numpy as np
import pandas as pd

from bokeh.palettes import Category20c, Category10
from bokeh.plotting import figure, show
from bokeh.transform import cumsum
from collections import Counter
from bokeh.layouts import row, column
from bokeh.models import (
    CustomJS, CustomJSFilter, RangeSlider, 
    ColumnDataSource, Slider, CDSView, 
    MultiChoice, LinearColorMapper, ColorBar,
    HoverTool
)
from bokeh.transform import transform


def plot_piechart(daten, merkmal):
    x = Counter(daten[merkmal])
    data = pd.Series(x).reset_index(name='value').rename(columns={'index': merkmal})
    data = data.sort_values(by=merkmal).set_index(merkmal).reset_index()
    data['angle'] = data['value']/data['value'].sum() * 2*pi
    if len(x) not in Category20c:
        data['color'] = Category10[max(3, len(x))][:len(x)]
    else:
        data['color'] = Category20c[len(x)]
    p1 = figure(height=350, width=300, title=f"Verteilung des Merkmals: {merkmal}", toolbar_location=None,
               tools="hover,box_zoom", tooltips=f"@{merkmal}: @value", x_range=(-0.5, 1.0))

    p1.wedge(x=0, y=1, radius=0.4,
            start_angle=cumsum('angle', include_zero=True), end_angle=cumsum('angle'),
            line_color="white", fill_color='color', legend_field=merkmal, source=data)

    p1.axis.axis_label = None
    p1.axis.visible = False
    p1.grid.grid_line_color = None
    return p1

def plot_histogram(daten, merkmal, label=None, title=None, bins=50):
    source = ColumnDataSource(daten)
    hist, edges = np.histogram(daten[merkmal], bins=bins, density=True)
    hist_df = ColumnDataSource(pd.DataFrame({'top': hist, 'left': edges[:-1], 'right': edges[1:]}))
    label = label if label is not None else merkmal
    title = title if title is not None else f"Histogram für Merkmal {merkmal}"
    slider = Slider(start=1, end=max(100, bins), value=bins, step=1, title="Anzahl Klassen")
    
    slider_callback = CustomJS(args=dict(slider=slider, source=source, merkmal=merkmal, hist=hist_df), code="""
        let bins = slider.value;        
        let values = source.data[merkmal];
        let min = Math.min(...values);
        let max = Math.max(...values);
        let size = (max - min) / bins;
        let left = [];
        let right = [];
        let frequency = [];
        for (let i=0;i<bins;i++) {
            left.push(min + i*size);
            right.push(min + (i+1)*size);
            frequency.push(0);
        }
        // Calculate frequency for each bin
        for (let i = 0; i < values.length; i++) {
            if (values[i]==min) frequency[0]++;
            else if (values[i]==max) frequency[bins-1]++;
            else frequency[Math.floor((values[i] - min) / size)]++;
        }
        for (let i=0;i<bins;i++) {
            frequency[i] /= values.length * size;
        }
        hist.data = {
            top: frequency,
            right: right,
            left: left
        };        
    """)
        
    slider.js_on_change("value", slider_callback)
    
    p = figure(
        title=title, background_fill_color="#fafafa",
        plot_height=400, plot_width=400
    )
    hist_plot = p.quad(source=hist_df, bottom=0, top='top', left='left', right='right',
                       fill_color="navy", line_color="white", alpha=0.5)
    p.add_tools(HoverTool(renderers=[hist_plot], tooltips="Density: @top{0.00000} (@left{0.0} - @right{0.0})"))
    
    xs = np.linspace(min(daten[merkmal]), max(daten[merkmal]), 100)
    ys = [stats.norm.pdf(x, loc=daten[merkmal].mean(), scale=daten[merkmal].std()) for x in xs]
    a, loc, scale = stats.skewnorm.fit(daten[merkmal])
    y_skewed = [stats.skewnorm.pdf(x, a=a, loc=loc, scale=scale) for x in xs]
    
    normal_dist_plot = p.line(xs, ys, color="orange", line_width=2, legend_label="Normalverteilung")
    p.add_tools(HoverTool(renderers=[normal_dist_plot], tooltips="Density: @y{0.00000} (@x{0.00000})"))
    
    skewed_dist_plot = p.line(
        xs, y_skewed, 
        color="red", line_width=2, line_dash="dashed",
        legend_label="Schiefe Normalverteilung"
    )
    p.add_tools(HoverTool(renderers=[skewed_dist_plot], tooltips="Density: @y{0.00000} (@x{0.00000})"))
    
    p.xaxis.axis_label = label
    p.yaxis.axis_label = 'Density'
    p.add_layout(p.legend[0], 'above')
    return column(slider, p)

def get_filter(ui_element, merkmal, js_condition):
    return CustomJSFilter(
        args=dict(ui_element=ui_element, merkmal=merkmal), 
        code=f"""
        let data = source.data;
        let x = data[merkmal];
        let indices = [];
        for (let i=0;i<x.length;i++) {{
            indices.push({js_condition});
        }}
        return indices;
        """
    )

def plot_merkmale(
    daten, 
    x='Groesse',
    y='Gewicht', 
    x_label=None,
    y_label=None,
    sliders=[],
    ranges=[],
    categorical=[],
    colorbar=None
):
    source = ColumnDataSource(daten)
    statistics = ColumnDataSource(pd.DataFrame(
        {
            'mean_x': [daten[x].mean()],
            'mean_y': [daten[y].mean()],
            'median_x': [daten[x].median()],
            'median_y': [daten[y].median()],
        }
    ))
    
    callback = CustomJS(args=dict(s=source), code="s.change.emit();")   
    
    ui_elements = []
    filters = []
    
    for name in sliders:
        slider = Slider(
            start=daten[name].min(),
            end=daten[name].max(),
            value=ceil(daten[name].max()),
            step=max(1, round((daten[name].max() - daten[name].min())/100)),
            title=f"{name} (max)"
        )
        filters.append(
            get_filter(
                ui_element=slider, 
                merkmal=name, 
                js_condition="x[i] <= ui_element.value")
        )
        slider.js_on_change('value', callback)
        ui_elements.append(slider)
        
    for name in ranges:
        slider = RangeSlider(
            title=name,
            start=daten[name].min(),
            end=daten[name].max(),
            value=(floor(daten[name].min()), ceil(daten[name].max())),
            step=max(1, round((daten[name].max() - daten[name].min())/100)),
        )
        filters.append(
            get_filter(
                ui_element=slider, 
                merkmal=name, 
                js_condition="(x[i] <= ui_element.value[1]) && (x[i] >= ui_element.value[0])")
        )
        slider.js_on_change('value', callback)
        ui_elements.append(slider)

    for name in categorical:
        values = [str(val) for val in sorted(list(set(daten[name])))]
        choice = MultiChoice(
            value=values,
            options=values,
            title=name
        )
        filters.append(
            get_filter(
                ui_element=choice, 
                merkmal=name, 
                js_condition="ui_element.value.indexOf(String(x[i])) > -1")
        )
        choice.js_on_change('value', callback)
        ui_elements.append(choice)
        
    view = CDSView(source=source, filters=filters)
        
    plot = figure(
        plot_width=800, 
        plot_height=400, 
        title=f"{x} vs. {y}",
        background_fill_color="#eee"
    )
    
    scatter_args = dict(
        x=x,
        y=y,
        line_width=3,
        line_alpha=0.3,
        size=5,
        view=view,
        source=source,
        marker="circle"
    )
    if colorbar is not None:
        color_mapper = LinearColorMapper(
            palette="Viridis256", 
            low=source.data[colorbar].min(), 
            high=source.data[colorbar].max()
        )
        color_bar = ColorBar(color_mapper=color_mapper, label_standoff=12, location=(0,0), title=colorbar)
        plot.add_layout(color_bar, 'right')
        scatter_args['color'] = transform(colorbar, color_mapper)
        
    circles = plot.scatter(**scatter_args)

        
    plot.add_tools(
        HoverTool(renderers=[circles], tooltips=" ".join([f"@{merkmal}" for merkmal in daten.columns]))
    )
        
    mean = plot.cross(
        'mean_x', 'mean_y', source=statistics, 
        size=30, color='red', line_width=2, legend_label="Mittelwert"
    )
    plot.add_tools(
        HoverTool(renderers=[mean], tooltips="Mittelwert:\n@mean_x{0.0} @mean_y{0.0}")
    )
    
    median = plot.scatter(
        'median_x', 'median_y', source=statistics, 
        size=30, color='orange', line_width=2, legend_label="Median", marker="x",
    )
    plot.add_tools(
        HoverTool(renderers=[median], tooltips="Median:\n@median_x{0.0} @median_y{0.0}")
    )
    
    plot.xaxis.axis_label = x_label if x_label is not None else x
    plot.yaxis.axis_label = y_label if y_label is not None else y
    
    return column(*ui_elements, plot)
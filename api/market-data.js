"use strict";
// Vercel function. Verified static aggregates; no raw listings or secrets.
// Quantiles describe asking price per m², in VND/m².
module.exports = async function handler(req,res) {
    res.setHeader('Content-Type','application/json; charset=utf-8');
    res.setHeader('Cache-Control','no-store');
    if(req.method !== 'GET'){res.setHeader('Allow','GET');return res.status(405).json({available:false,resolution_level:'NONE',reason:'method_not_allowed',live_connected:false});}
    const params={province:req.query?.province ?? '',ward:req.query?.ward ?? '',sub_area:req.query?.sub_area ?? '',area:req.query?.area ?? '',property_type:req.query?.property_type ?? ''};
    if(Object.values(params).some(v=>typeof v!=='string'||v.length>200||/[\u0000-\u001f]/.test(v)))return res.status(400).json({available:false,resolution_level:'NONE',reason:'invalid_parameters'});
    if(req.query?.area_m2!==undefined){if(typeof req.query.area_m2!=='string'||!req.query.area_m2.trim())return res.status(400).json({available:false,resolution_level:'NONE',reason:'invalid_area'});params.area_m2=Number(req.query.area_m2);}
    let staticData;
    try { staticData = require('../data/vietnam-market-stats.json'); }
    catch { return res.status(503).json({available:false,resolution_level:'NONE',reason:'unavailable',live_connected:false}); }
    if(!Array.isArray(staticData?.stats))return res.status(503).json({available:false,resolution_level:'NONE',reason:'unavailable',live_connected:false});
    try {
        const index=require('../data/vietnam-location-index.json'),core=require('../vietnam-estimate-core.js');
        const result=core.resolve(staticData,index,params);
        return res.status(result.reason==='unavailable'?503:['invalid_parameters','invalid_area'].includes(result.reason)?400:200).json(result);
    } catch {return res.status(503).json({available:false,resolution_level:'NONE',reason:'unavailable',live_connected:false});}

};
